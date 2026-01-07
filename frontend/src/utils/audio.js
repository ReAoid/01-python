/**
 * 音频管理器 (Audio Manager)
 * -------------------------------------------------------------------------
 * 负责处理 PCM 音频的播放和录制，支持流式音频处理。
 * 
 * 主要功能:
 * 1. 音频播放 (Playback): 接收后端发送的 PCM 数据并实时播放
 * 2. 音频录制 (Recording): 捕获麦克风输入并编码为 PCM 格式
 * 3. 采样率转换 (Resampling): 自动适配不同设备的音频采样率
 * 4. 字节流重组 (Byte Alignment): 处理网络传输中的数据分包问题
 */
export class AudioManager {
    /**
     * 构造函数
     * 初始化音频管理器的各项状态和缓冲区
     */
    constructor() {
        // Web Audio API 上下文 (用于所有音频操作)
        this.audioContext = null;
        
        // 录音状态标志
        this.isRecording = false;
        
        // =========================================================================
        // 录音相关属性 (Recording Properties)
        // =========================================================================
        this.mediaStream = null;          // 麦克风媒体流
        this.recorderProcessor = null;    // 录音处理节点
        this.inputSource = null;          // 音频源节点

        // =========================================================================
        // 播放相关属性 (Playback Properties)
        // =========================================================================
        this.playerProcessor = null;      // 播放处理节点
        this.audioQueue = [];             // PCM 数据队列 (Float32Array[])
        this.isPlaying = false;           // 播放状态标志
        this.inputSampleRate = 32000;     // 后端音频采样率 (Hz)
        
        // =========================================================================
        // 音频处理缓冲区 (Audio Processing Buffers)
        // =========================================================================
        this.resampleLeftover = null;     // 重采样剩余数据
        this.byteLeftover = null;         // 字节流重组缓冲区 (处理未对齐数据)
    }

    /**
     * 初始化音频上下文
     * 创建 Web Audio API 的核心对象，兼容不同浏览器
     */
    _initAudioContext() {
        if (!this.audioContext) {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                // 建议浏览器使用此采样率，但不一定保证
                // 实际采样率由设备硬件决定，我们会在录音时手动重采样
            });
        }
    }

    // =========================================================================
    // 音频播放模块 (Playback Module)
    // =========================================================================
    
    /**
     * 播放 PCM 音频数据
     * 使用 ScriptProcessorNode 实现流式播放，消除音频拼接产生的噪声
     * 
     * @param {ArrayBuffer} data - 原始音频数据 (16-bit PCM, 32000Hz, Mono)
     */
    async playPCM(data) {
        this._initAudioContext();
        
        // 恢复 Context
        if (this.audioContext.state === 'suspended') {
            await this.audioContext.resume();
        }

        // 1. 获取 ArrayBuffer
        let chunk = data;
        if (data.buffer) {
             chunk = data.buffer;
        }

        // 2. 字节流重组逻辑
        // 如果有上次剩下的字节，先拼接到当前块前面
        if (this.byteLeftover) {
            const newChunk = new Uint8Array(this.byteLeftover.byteLength + chunk.byteLength);
            newChunk.set(new Uint8Array(this.byteLeftover));
            newChunk.set(new Uint8Array(chunk), this.byteLeftover.byteLength);
            chunk = newChunk.buffer;
            this.byteLeftover = null;
        }

        // 检查是否对齐 (字节数必须是 2 的倍数)
        if (chunk.byteLength % 2 !== 0) {
            // 切分：前面的偶数部分拿去播放，剩下的 1 字节留到下次
            const validLength = chunk.byteLength - 1;
            this.byteLeftover = chunk.slice(validLength); // 保存最后 1 字节
            chunk = chunk.slice(0, validLength); // 只保留偶数长度部分
        }
        
        // 如果 chunk 为空 (比如只发来了 1 个字节)，直接返回等待下一次
        if (chunk.byteLength === 0) return;

        // 3. 解析 PCM 数据 (Int16 -> Float32)
        const int16Array = new Int16Array(chunk);
        const float32Array = new Float32Array(int16Array.length);
        for (let i = 0; i < int16Array.length; i++) {
            float32Array[i] = int16Array[i] / 32768.0;
        }

        // 4. 将数据推入队列
        this.audioQueue.push(float32Array);

        // 5. 如果播放器未启动，则启动
        if (!this.isPlaying) {
            console.log("[AudioManager] Starting playback stream...");
            this._startStreamingPlayback();
        }
    }

    /**
     * 启动流式音频播放
     * 创建音频处理节点并连接到输出设备
     */
    _startStreamingPlayback() {
        if (this.isPlaying) return;
        this.isPlaying = true;

        // 恢复音频上下文 (某些浏览器会自动挂起)
        if (this.audioContext.state === 'suspended') {
            this.audioContext.resume().then(() => {
                console.log("[AudioManager] AudioContext resumed successfully");
            });
        }

        // 创建音频处理节点
        // bufferSize: 4096 样本 (延迟约 90ms @ 44.1kHz)
        // inputChannels: 0 (不需要输入)
        // outputChannels: 1 (单声道输出)
        this.playerProcessor = this.audioContext.createScriptProcessor(4096, 0, 1);

        // 音频处理回调: 每次需要填充音频缓冲区时触发
        this.playerProcessor.onaudioprocess = (e) => {
            const outputData = e.outputBuffer.getChannelData(0);
            const outputLength = outputData.length;

            // [关键] 如果 queue 为空且没有 leftover，直接填充静音并返回
            // 避免下面的逻辑在没有数据时产生错误的静音处理或死循环
            if ((!this.resampleLeftover || this.resampleLeftover.length === 0) && this.audioQueue.length === 0) {
                for (let i = 0; i < outputLength; i++) {
                    outputData[i] = 0;
                }
                return;
            }

            // 目标: 填满输出缓冲区
            let outputIndex = 0;              // 当前输出位置
            let hasData = false;              // 是否有有效音频数据
            
            // 安全守卫: 防止无限循环
            let loopGuard = 0;
            
            while (outputIndex < outputLength) {
                loopGuard++;
                if (loopGuard > 5000) { 
                    console.error("[AudioManager] Infinite loop detected in playback processor!");
                    break;
                }

                // 1. 如果没有剩余数据，尝试从队列获取
                if (!this.resampleLeftover || this.resampleLeftover.length === 0) {
                    if (this.audioQueue.length > 0) {
                        this.resampleLeftover = this.audioQueue.shift();
                    } else {
                        // 队列空了：填充静音并退出
                        for (let i = outputIndex; i < outputLength; i++) {
                            outputData[i] = 0;
                        }
                        return;
                    }
                }

                const ratio = this.inputSampleRate / this.audioContext.sampleRate;
                
                // 2. 计算当前 leftover 能提供的输出点数
                const inputAvailable = this.resampleLeftover.length;
                // 计算当前可生成的输出点数（不减 1，允许用到最后一个点）
                // 线性插值通常需要 i 和 i+1，但在数据流的末尾，我们可能需要特殊处理
                // 为了简化且防止死循环，我们使用 Math.floor(inputAvailable / ratio)
                // 这可能导致最后一个采样点被丢弃或产生微小的不连续，但比死循环好
                let outputCanGenerate = Math.floor(inputAvailable / ratio);
                
                // 3. 边界情况：如果 leftover 数据太少，不够生成哪怕 1 个点
                if (outputCanGenerate <= 0) {
                    if (this.audioQueue.length > 0) {
                        // 拼接到下一个块
                        const nextChunk = this.audioQueue.shift();
                        const newChunk = new Float32Array(this.resampleLeftover.length + nextChunk.length);
                        newChunk.set(this.resampleLeftover);
                        newChunk.set(nextChunk, this.resampleLeftover.length);
                        this.resampleLeftover = newChunk;
                        continue;
                    } else {
                        // 没数据了，直接退出（剩余的 output 填静音）
                        for (let i = outputIndex; i < outputLength; i++) {
                            outputData[i] = 0;
                        }
                        this.resampleLeftover = null;
                        return; 
                    }
                }
                
                // 4. 本次循环要处理的输出点数
                const processCount = Math.min(outputLength - outputIndex, outputCanGenerate);
                
                // 5. 执行线性插值
                for (let i = 0; i < processCount; i++) {
                    const inputIdx = i * ratio;
                    const idxFloor = Math.floor(inputIdx);
                    // 安全检查：防止 idxCeil 越界
                    const idxCeil = Math.min(idxFloor + 1, this.resampleLeftover.length - 1);
                    const alpha = inputIdx - idxFloor;
                    
                    const val = this.resampleLeftover[idxFloor] * (1 - alpha) + 
                                this.resampleLeftover[idxCeil] * alpha;
                    
                    outputData[outputIndex + i] = val;
                    if (Math.abs(val) > 0.0001) hasData = true;
                }
                
                // [关键] 必须增加 outputIndex
                outputIndex += processCount;
                
                // 6. 消耗输入数据
                const inputConsumed = Math.floor(processCount * ratio);
                if (inputConsumed >= this.resampleLeftover.length) {
                    this.resampleLeftover = null;
                } else {
                    this.resampleLeftover = this.resampleLeftover.subarray(inputConsumed);
                }
            }
        };

        // 连接到音频输出设备
        this.playerProcessor.connect(this.audioContext.destination);
    }
    
    /**
     * 停止音频播放
     * 断开音频节点并清空缓冲区
     */
    stopPlayback() {
        if (this.playerProcessor) {
            this.playerProcessor.disconnect();
            this.playerProcessor = null;
        }
        this.isPlaying = false;
        this.audioQueue = [];
        this.resampleLeftover = null;
        this.byteLeftover = null;

        // [双重保险] 挂起 AudioContext 可以立即停止硬件缓冲区的剩余声音
        if (this.audioContext && this.audioContext.state === 'running') {
            this.audioContext.suspend();
        }
    }

    // =========================================================================
    // 音频录制模块 (Recording Module)
    // =========================================================================
    
    /**
     * 开始录音
     * 请求麦克风权限并开始捕获音频数据
     * 
     * @param {Function} onData - 数据回调函数
     *                            参数: ArrayBuffer (16kHz, 16-bit PCM, Mono)
     */
    async startRecording(onData) {
        this._initAudioContext();
        
        if (this.audioContext.state === 'suspended') {
            await this.audioContext.resume();
        }

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.mediaStream = stream;
            this.isRecording = true;

            // 获取设备音频采样率和目标采样率
            const sourceSampleRate = this.audioContext.sampleRate;  // 设备原始采样率
            const targetSampleRate = 16000;                          // 目标采样率 (后端要求)

            // 创建音频源节点
            this.inputSource = this.audioContext.createMediaStreamSource(stream);
            
            // 创建音频处理节点
            // bufferSize: 4096 样本 (每次回调处理的数据量)
            // inputChannels: 1 (单声道输入)
            // outputChannels: 1 (需要连接到输出，但会静音)
            this.processor = this.audioContext.createScriptProcessor(4096, 1, 1);

            // 音频处理回调: 处理麦克风捕获的音频数据
            this.processor.onaudioprocess = (e) => {
                if (!this.isRecording) return;
                
                // 1. 获取输入音频数据 (Float32Array)
                const inputData = e.inputBuffer.getChannelData(0);
                
                // 2. 重采样: 将设备采样率转换为目标采样率
                const downsampledData = this._downsampleBuffer(inputData, sourceSampleRate, targetSampleRate);
                
                // 3. 格式转换: Float32 -> Int16 PCM
                const pcmData = this._floatTo16BitPCM(downsampledData);
                
                // 4. 通过回调发送 PCM 数据
                if (onData && pcmData.byteLength > 0) {
                    onData(pcmData);
                }
            };

            // 连接音频节点链路
            // 注意: ScriptProcessorNode 必须连接到 destination 才能工作
            // 为了避免听到自己的声音，使用增益为 0 的 GainNode
            const gainNode = this.audioContext.createGain();
            gainNode.gain.value = 0;  // 静音
            
            this.inputSource.connect(this.processor);
            this.processor.connect(gainNode);
            gainNode.connect(this.audioContext.destination);

        } catch (error) {
            console.error('Error accessing microphone:', error);
            throw error;
        }
    }

    /**
     * 停止录音
     * 释放麦克风资源并断开音频节点
     */
    stopRecording() {
        this.isRecording = false;
        
        if (this.mediaStream) {
            this.mediaStream.getTracks().forEach(track => track.stop());
            this.mediaStream = null;
        }
        
        if (this.processor) {
            this.processor.disconnect();
            this.processor = null;
        }
        
        if (this.inputSource) {
            this.inputSource.disconnect();
            this.inputSource = null;
        }
    }

    /**
     * 音频重采样 (降采样)
     * 将高采样率音频转换为低采样率
     * 
     * @param {Float32Array} buffer - 输入音频数据
     * @param {number} sampleRate - 原始采样率
     * @param {number} outSampleRate - 目标采样率
     * @returns {Float32Array} 重采样后的音频数据
     */
    _downsampleBuffer(buffer, sampleRate, outSampleRate) {
        // 采样率相同，无需处理
        if (outSampleRate === sampleRate) {
            return buffer;
        }
        
        // 不支持上采样 (暂无需求)
        if (outSampleRate > sampleRate) {
            return buffer;
        }
        
        const sampleRateRatio = sampleRate / outSampleRate;
        const newLength = Math.round(buffer.length / sampleRateRatio);
        const result = new Float32Array(newLength);
        
        let offsetResult = 0;
        let offsetBuffer = 0;
        
        while (offsetResult < result.length) {
            const nextOffsetBuffer = Math.round((offsetResult + 1) * sampleRateRatio);
            
            let accum = 0, count = 0;
            for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
                accum += buffer[i];
                count++;
            }
            
            result[offsetResult] = count > 0 ? accum / count : 0;
            offsetResult++;
            offsetBuffer = nextOffsetBuffer;
        }
        
        return result;
    }

    /**
     * 音频格式转换: Float32 -> Int16 PCM
     * Web Audio API 使用 [-1.0, 1.0] 的浮点数表示音频
     * PCM 格式使用 16-bit 整数表示音频
     * 
     * @param {Float32Array} output - Float32 音频数据
     * @returns {ArrayBuffer} Int16 PCM 音频数据
     */
    _floatTo16BitPCM(output) {
        // 创建输出缓冲区 (每个样本 2 字节)
        const buffer = new ArrayBuffer(output.length * 2);
        const view = new DataView(buffer);
        
        // 转换每个样本
        for (let i = 0; i < output.length; i++) {
            // 1. 限制范围到 [-1.0, 1.0]
            let s = Math.max(-1, Math.min(1, output[i]));
            // 2. 缩放到 Int16 范围 [-32768, 32767]
            s = s < 0 ? s * 0x8000 : s * 0x7FFF;
            // 3. 写入缓冲区 (Little-endian 字节序)
            view.setInt16(i * 2, s, true);
        }
        return buffer;
    }
}
