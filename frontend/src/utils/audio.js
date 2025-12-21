/**
 * 音频管理器
 * 负责处理 PCM 音频的播放和录制
 */
export class AudioManager {
    constructor() {
        this.audioContext = null;
        this.isRecording = false;
        
        // 录音相关
        this.mediaStream = null;
        this.recorderProcessor = null;
        this.inputSource = null;

        // 播放相关
        this.playerProcessor = null;
        this.audioQueue = []; // 存放 Float32 的 PCM 数据块
        this.isPlaying = false;
        this.inputSampleRate = 32000; // 后端发来的采样率
        
        // 重采样状态
        this.resampleLeftover = null;
        
        // 字节流重组缓冲区 (处理 misaligned data)
        this.byteLeftover = null;
    }

    _initAudioContext() {
        if (!this.audioContext) {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                // 建议浏览器使用此采样率，但不一定保证
                // 我们会在录音时手动重采样
            });
        }
    }

    // --- 播放部分 ---
    
    /**
     * 播放 PCM 数据片段
     * 改用 ScriptProcessorNode 实现流式播放，消除拼接噪声
     * @param {ArrayBuffer} data - 16-bit PCM, 32000Hz, Mono
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

    _startStreamingPlayback() {
        if (this.isPlaying) return;
        this.isPlaying = true;

        if (this.audioContext.state === 'suspended') {
            this.audioContext.resume().then(() => {
                console.log("[AudioManager] AudioContext resumed successfully");
            });
        }

        // 创建 ScriptProcessorNode
        // bufferSize: 4096 (延迟约 90ms @ 44.1k), input: 0, output: 1
        this.playerProcessor = this.audioContext.createScriptProcessor(4096, 0, 1);
        
        let debugCounter = 0; // 限制日志频率

        this.playerProcessor.onaudioprocess = (e) => {
            const outputData = e.outputBuffer.getChannelData(0);
            const outputLength = outputData.length;
            
            // 调试：每 100 次回调 (约 8-9秒) 打印一次状态，或者在刚开始时打印
            debugCounter++;
            // if (debugCounter === 1 || debugCounter % 100 === 0) {
            //      console.log(`[AudioDebug] ctx.state=${this.audioContext.state}, ctx.rate=${this.audioContext.sampleRate}, queueLen=${this.audioQueue.length}, leftover=${this.resampleLeftover ? this.resampleLeftover.length : 0}`);
            // }

            // [关键] 如果 queue 为空且没有 leftover，直接填充静音并返回
            // 避免下面的逻辑在没有数据时产生错误的静音处理或死循环
            if ((!this.resampleLeftover || this.resampleLeftover.length === 0) && this.audioQueue.length === 0) {
                for (let i = 0; i < outputLength; i++) {
                    outputData[i] = 0;
                }
                // if (debugCounter % 50 === 0) {
                //      console.debug("[AudioManager] Buffer underrun (Empty)");
                // }
                return;
            }

            // 目标: 填满 outputData
            let outputIndex = 0;
            let hasData = false;
            
            // 安全守卫
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

        this.playerProcessor.connect(this.audioContext.destination);
    }
    
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

    // --- 录音部分 ---
    
    /**
     * 开始录音
     * @param {Function} onData - 回调函数，接收 ArrayBuffer (16k 16-bit PCM)
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

            const sourceSampleRate = this.audioContext.sampleRate;
            const targetSampleRate = 16000;

            this.inputSource = this.audioContext.createMediaStreamSource(stream);
            
            // 使用 ScriptProcessorNode (bufferSize, inputChannels, outputChannels)
            // 4096 帧触发一次回调
            this.processor = this.audioContext.createScriptProcessor(4096, 1, 1);

            this.processor.onaudioprocess = (e) => {
                if (!this.isRecording) return;
                
                const inputData = e.inputBuffer.getChannelData(0);
                
                // 重采样
                const downsampledData = this._downsampleBuffer(inputData, sourceSampleRate, targetSampleRate);
                
                // Float32 -> Int16 PCM
                const pcmData = this._floatTo16BitPCM(downsampledData);
                
                // 回调发送
                if (onData && pcmData.byteLength > 0) {
                    onData(pcmData);
                }
            };

            // 为了让 ScriptProcessor 工作，它必须连接到 destination
            // 但我们不希望听到自己的声音，所以通过一个 Gain 为 0 的节点连接
            const gainNode = this.audioContext.createGain();
            gainNode.gain.value = 0;
            
            this.inputSource.connect(this.processor);
            this.processor.connect(gainNode);
            gainNode.connect(this.audioContext.destination);

        } catch (error) {
            console.error('Error accessing microphone:', error);
            throw error;
        }
    }

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

    _downsampleBuffer(buffer, sampleRate, outSampleRate) {
        if (outSampleRate === sampleRate) {
            return buffer;
        }
        
        if (outSampleRate > sampleRate) {
            // 上采样暂不支持，也不需要
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

    _floatTo16BitPCM(output) {
        const buffer = new ArrayBuffer(output.length * 2);
        const view = new DataView(buffer);
        
        for (let i = 0; i < output.length; i++) {
            let s = Math.max(-1, Math.min(1, output[i]));
            s = s < 0 ? s * 0x8000 : s * 0x7FFF;
            view.setInt16(i * 2, s, true); // Little-endian
        }
        return buffer;
    }
}
