/**
 * 音频录制工具 - 录制 WAV 格式音频
 * 使用 Web Audio API 直接生成 WAV 格式，避免浏览器默认的 webm/ogg 格式
 */

export class AudioRecorder {
  constructor(sampleRate = 16000) {
    this.sampleRate = sampleRate
    this.audioContext = null
    this.mediaStream = null
    this.mediaStreamSource = null
    this.processor = null
    this.audioChunks = []
    this.isRecording = false
  }

  /**
   * 开始录音
   */
  async start() {
    try {
      // 获取麦克风权限
      this.mediaStream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          sampleRate: this.sampleRate,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        } 
      })

      // 创建音频上下文
      this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
        sampleRate: this.sampleRate
      })

      // 创建音频源
      this.mediaStreamSource = this.audioContext.createMediaStreamSource(this.mediaStream)

      // 创建处理器节点（使用较大的缓冲区）
      const bufferSize = 4096
      this.processor = this.audioContext.createScriptProcessor(bufferSize, 1, 1)

      // 重置音频块
      this.audioChunks = []
      this.isRecording = true

      // 处理音频数据
      this.processor.onaudioprocess = (e) => {
        if (!this.isRecording) return

        const inputData = e.inputBuffer.getChannelData(0)
        // 复制数据（避免引用问题）
        const chunk = new Float32Array(inputData)
        this.audioChunks.push(chunk)
      }

      // 连接节点
      this.mediaStreamSource.connect(this.processor)
      this.processor.connect(this.audioContext.destination)

      console.log('[AudioRecorder] Recording started', {
        sampleRate: this.audioContext.sampleRate,
        bufferSize
      })

      return true
    } catch (error) {
      console.error('[AudioRecorder] Failed to start recording:', error)
      throw error
    }
  }

  /**
   * 停止录音并返回 WAV Blob
   */
  async stop() {
    if (!this.isRecording) {
      throw new Error('Not recording')
    }

    this.isRecording = false

    // 断开节点
    if (this.processor) {
      this.processor.disconnect()
      this.processor = null
    }

    if (this.mediaStreamSource) {
      this.mediaStreamSource.disconnect()
      this.mediaStreamSource = null
    }

    // 停止媒体流
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach(track => track.stop())
      this.mediaStream = null
    }

    // 关闭音频上下文
    if (this.audioContext) {
      await this.audioContext.close()
      this.audioContext = null
    }

    // 合并所有音频块
    const audioData = this.mergeAudioChunks(this.audioChunks)

    // 转换为 WAV 格式
    const wavBlob = this.encodeWAV(audioData, this.sampleRate)

    console.log('[AudioRecorder] Recording stopped', {
      duration: audioData.length / this.sampleRate,
      size: wavBlob.size
    })

    return wavBlob
  }

  /**
   * 合并音频块
   */
  mergeAudioChunks(chunks) {
    const totalLength = chunks.reduce((acc, chunk) => acc + chunk.length, 0)
    const result = new Float32Array(totalLength)
    
    let offset = 0
    for (const chunk of chunks) {
      result.set(chunk, offset)
      offset += chunk.length
    }
    
    return result
  }

  /**
   * 将 Float32Array 音频数据编码为 WAV 格式
   */
  encodeWAV(samples, sampleRate) {
    const buffer = new ArrayBuffer(44 + samples.length * 2)
    const view = new DataView(buffer)

    // WAV 文件头
    // RIFF chunk descriptor
    this.writeString(view, 0, 'RIFF')
    view.setUint32(4, 36 + samples.length * 2, true)
    this.writeString(view, 8, 'WAVE')

    // FMT sub-chunk
    this.writeString(view, 12, 'fmt ')
    view.setUint32(16, 16, true) // fmt chunk size
    view.setUint16(20, 1, true) // audio format (1 = PCM)
    view.setUint16(22, 1, true) // number of channels
    view.setUint32(24, sampleRate, true) // sample rate
    view.setUint32(28, sampleRate * 2, true) // byte rate
    view.setUint16(32, 2, true) // block align
    view.setUint16(34, 16, true) // bits per sample

    // Data sub-chunk
    this.writeString(view, 36, 'data')
    view.setUint32(40, samples.length * 2, true)

    // 写入 PCM 数据（Float32 转 Int16）
    this.floatTo16BitPCM(view, 44, samples)

    return new Blob([view], { type: 'audio/wav' })
  }

  /**
   * 写入字符串到 DataView
   */
  writeString(view, offset, string) {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i))
    }
  }

  /**
   * 将 Float32Array 转换为 16-bit PCM
   */
  floatTo16BitPCM(view, offset, input) {
    for (let i = 0; i < input.length; i++, offset += 2) {
      const s = Math.max(-1, Math.min(1, input[i]))
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true)
    }
  }

  /**
   * 取消录音
   */
  cancel() {
    this.isRecording = false

    if (this.processor) {
      this.processor.disconnect()
      this.processor = null
    }

    if (this.mediaStreamSource) {
      this.mediaStreamSource.disconnect()
      this.mediaStreamSource = null
    }

    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach(track => track.stop())
      this.mediaStream = null
    }

    if (this.audioContext) {
      this.audioContext.close()
      this.audioContext = null
    }

    this.audioChunks = []
  }
}
