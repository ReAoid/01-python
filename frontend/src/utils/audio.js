/**
 * 音频管理器
 * 负责处理 PCM 音频的播放和录制
 */
export class AudioManager {
    constructor() {
        this.audioContext = null;
        this.nextStartTime = 0;
        this.isRecording = false;
        this.mediaStream = null;
        this.processor = null;
        this.inputSource = null;
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
     * @param {ArrayBuffer} data - 16-bit PCM, 16000Hz, Mono
     */
    async playPCM(data) {
        this._initAudioContext();
        
        // 如果 Context 处于挂起状态（由于自动播放策略），则恢复它
        if (this.audioContext.state === 'suspended') {
            await this.audioContext.resume();
        }

        // 16-bit PCM 转 Float32
        const int16Array = new Int16Array(data);
        const float32Array = new Float32Array(int16Array.length);
        
        for (let i = 0; i < int16Array.length; i++) {
            float32Array[i] = int16Array[i] / 32768.0;
        }

        // 创建 AudioBuffer (单声道，采样率 16000)
        const buffer = this.audioContext.createBuffer(1, float32Array.length, 16000);
        buffer.getChannelData(0).set(float32Array);

        // 创建 Source
        const source = this.audioContext.createBufferSource();
        source.buffer = buffer;
        source.connect(this.audioContext.destination);

        // 调度播放时间，实现无缝衔接
        const currentTime = this.audioContext.currentTime;
        if (this.nextStartTime < currentTime) {
            this.nextStartTime = currentTime;
        }
        
        source.start(this.nextStartTime);
        
        // 更新下一次播放的开始时间
        this.nextStartTime += buffer.duration;
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

