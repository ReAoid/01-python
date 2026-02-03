<script setup>
/**
 * TTS 测试面板组件（弹窗模式）
 * -------------------------------------------------------------------------
 * 提供 TTS 服务状态检测和语音生成测试功能
 */

import { ref, onMounted } from 'vue'

// Emits
const emit = defineEmits(['close'])

// 状态
const ttsStatus = ref(null)
const isCheckingStatus = ref(false)
const isGenerating = ref(false)

// 测试文本
const testText = ref('你好，这是一个语音测试。')

// 关闭弹窗
const closeModal = () => {
  emit('close')
}

// 检查 TTS 状态
const checkStatus = async () => {
  isCheckingStatus.value = true
  
  try {
    const response = await fetch('/api/tts/status')
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    const data = await response.json()
    ttsStatus.value = data
    
    console.log('[TTS] Status:', data)
  } catch (error) {
    console.error('[TTS] Failed to check status:', error)
    ttsStatus.value = {
      enabled: false,
      running: false,
      message: `检查失败: ${error.message}`
    }
  } finally {
    isCheckingStatus.value = false
  }
}

// 将 PCM 数据转换为 WAV 格式
const pcmToWav = (pcmData, sampleRate, channels, sampleWidth) => {
  const dataLength = pcmData.byteLength
  const buffer = new ArrayBuffer(44 + dataLength)
  const view = new DataView(buffer)
  
  // WAV 文件头
  // "RIFF" chunk descriptor
  writeString(view, 0, 'RIFF')
  view.setUint32(4, 36 + dataLength, true)
  writeString(view, 8, 'WAVE')
  
  // "fmt " sub-chunk
  writeString(view, 12, 'fmt ')
  view.setUint32(16, 16, true) // fmt chunk size
  view.setUint16(20, 1, true) // audio format (1 = PCM)
  view.setUint16(22, channels, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * channels * sampleWidth, true) // byte rate
  view.setUint16(32, channels * sampleWidth, true) // block align
  view.setUint16(34, sampleWidth * 8, true) // bits per sample
  
  // "data" sub-chunk
  writeString(view, 36, 'data')
  view.setUint32(40, dataLength, true)
  
  // 写入 PCM 数据
  const pcmView = new Uint8Array(pcmData)
  const wavView = new Uint8Array(buffer)
  wavView.set(pcmView, 44)
  
  return new Blob([buffer], { type: 'audio/wav' })
}

// 辅助函数：写入字符串到 DataView
const writeString = (view, offset, string) => {
  for (let i = 0; i < string.length; i++) {
    view.setUint8(offset + i, string.charCodeAt(i))
  }
}

// 生成语音测试
const generateSpeech = async () => {
  if (!testText.value.trim()) {
    alert('请输入测试文本')
    return
  }
  
  isGenerating.value = true
  
  try {
    const response = await fetch('/api/tts/test', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        text: testText.value
      })
    })
    
    if (!response.ok) {
      const errorText = await response.text()
      let errorDetail = '生成失败'
      try {
        const error = JSON.parse(errorText)
        errorDetail = error.detail || errorDetail
      } catch {
        errorDetail = errorText
      }
      throw new Error(errorDetail)
    }
    
    // 获取响应头中的音频参数
    const sampleRate = parseInt(response.headers.get('X-Sample-Rate') || '32000')
    const channels = parseInt(response.headers.get('X-Channels') || '1')
    const sampleWidth = parseInt(response.headers.get('X-Sample-Width') || '2')
    
    // 获取 PCM 音频数据
    const pcmData = await response.arrayBuffer()
    
    // 将 PCM 转换为 WAV 格式
    const wavBlob = pcmToWav(pcmData, sampleRate, channels, sampleWidth)
    
    // 创建音频 URL
    const audioUrl = URL.createObjectURL(wavBlob)
    
    // 播放音频
    const audio = new Audio(audioUrl)
    audio.play()
    
    // 清理
    audio.onended = () => {
      URL.revokeObjectURL(audioUrl)
    }
    
    console.log('[TTS] Speech generated successfully')
  } catch (error) {
    console.error('[TTS] Failed to generate speech:', error)
    alert(`生成语音失败: ${error.message}`)
  } finally {
    isGenerating.value = false
  }
}

// 组件挂载时检查状态
onMounted(() => {
  checkStatus()
})
</script>

<template>
  <!-- 弹窗遮罩 -->
  <div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" @click.self="closeModal">
    <!-- 弹窗内容 -->
    <div class="bg-white rounded-lg shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col">
      <!-- 标题栏 -->
      <div class="px-6 py-4 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
        <h4 class="font-semibold text-gray-900 flex items-center gap-2">
          <i class="fas fa-volume-up text-green-500"></i>
          TTS 测试面板
        </h4>
        <button 
          @click="closeModal"
          class="text-gray-400 hover:text-gray-600 transition-colors"
        >
          <i class="fas fa-times text-xl"></i>
        </button>
      </div>
      
      <!-- 滚动内容区域 -->
      <div class="overflow-y-auto flex-1">
    
    <div class="p-6 space-y-6">
      <!-- 状态信息 -->
      <div>
        <div class="flex items-center justify-between mb-3">
          <h5 class="text-sm font-semibold text-gray-700">服务状态</h5>
          <button 
            @click="checkStatus"
            :disabled="isCheckingStatus"
            class="px-3 py-1.5 bg-blue-500 text-white rounded-lg text-sm hover:bg-blue-600 transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            <i class="fas fa-sync" :class="{ 'fa-spin': isCheckingStatus }"></i>
            {{ isCheckingStatus ? '检查中...' : '刷新状态' }}
          </button>
        </div>
        
        <!-- 状态显示 -->
        <div v-if="ttsStatus" class="space-y-2">
          <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <span class="text-sm text-gray-600">启用状态</span>
            <span class="px-2 py-1 rounded-full text-xs font-medium"
                  :class="ttsStatus.enabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'">
              {{ ttsStatus.enabled ? '已启用' : '未启用' }}
            </span>
          </div>
          
          <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <span class="text-sm text-gray-600">运行状态</span>
            <span class="px-2 py-1 rounded-full text-xs font-medium"
                  :class="ttsStatus.running ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-600'">
              {{ ttsStatus.running ? '运行中' : '未运行' }}
            </span>
          </div>
          
          <div v-if="ttsStatus.server_url" class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <span class="text-sm text-gray-600">服务地址</span>
            <span class="text-sm font-mono text-gray-900">{{ ttsStatus.server_url }}</span>
          </div>
          
          <div v-if="ttsStatus.engine" class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <span class="text-sm text-gray-600">引擎</span>
            <span class="text-sm font-medium text-gray-900">{{ ttsStatus.engine }}</span>
          </div>
          
          <div v-if="ttsStatus.character" class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <span class="text-sm text-gray-600">角色</span>
            <span class="text-sm font-medium text-gray-900">{{ ttsStatus.character }}</span>
          </div>
          
          <!-- 消息提示 -->
          <div v-if="ttsStatus.message" 
               class="p-3 rounded-lg"
               :class="ttsStatus.running ? 'bg-green-50 text-green-700' : 'bg-yellow-50 text-yellow-700'">
            <p class="text-sm">{{ ttsStatus.message }}</p>
            <p v-if="ttsStatus.hint" class="text-xs mt-1">{{ ttsStatus.hint }}</p>
          </div>
        </div>
        
        <!-- 加载中 -->
        <div v-else class="flex items-center justify-center py-8 text-gray-400">
          <i class="fas fa-spinner fa-spin text-2xl"></i>
        </div>
      </div>
      
      <!-- 语音生成测试 -->
      <div class="pt-6 border-t border-gray-200">
        <h5 class="text-sm font-semibold text-gray-700 mb-3">语音生成测试</h5>
        
        <div class="space-y-3">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">测试文本</label>
            <textarea 
              v-model="testText"
              rows="3"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none"
              placeholder="输入要转换为语音的文本..."
            ></textarea>
            <p class="text-xs text-gray-500 mt-1">建议长度: 10-100 字</p>
          </div>
          
          <button 
            @click="generateSpeech"
            :disabled="!testText.trim() || isGenerating || !ttsStatus?.running"
            class="w-full px-4 py-3 bg-green-500 text-white rounded-lg hover:bg-green-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            <i class="fas" :class="isGenerating ? 'fa-spinner fa-spin' : 'fa-play'"></i>
            {{ isGenerating ? '生成中...' : '生成并播放语音' }}
          </button>
          
          <!-- 提示信息 -->
          <div v-if="!ttsStatus?.running" class="p-3 bg-yellow-50 text-yellow-700 rounded-lg">
            <p class="text-sm">
              <i class="fas fa-exclamation-triangle mr-2"></i>
              TTS 服务未运行，请先启动服务
            </p>
            <p class="text-xs mt-1">启动命令: <code class="bg-yellow-100 px-2 py-0.5 rounded">python backend/genie_server.py</code></p>
          </div>
        </div>
      </div>
      </div>
    </div>
    </div>
  </div>
</template>
