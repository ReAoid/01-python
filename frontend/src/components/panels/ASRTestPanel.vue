<script setup>
/**
 * ASR 测试面板组件（弹窗模式）
 * -------------------------------------------------------------------------
 * 提供 ASR 音频上传和麦克风录音测试功能，支持实时文本展示
 */

import { ref, onMounted, nextTick } from 'vue'
import { AudioRecorder } from '../../utils/audioRecorder.js'

// Emits
const emit = defineEmits(['close'])

// 状态
const asrStatus = ref(null)
const isCheckingStatus = ref(false)
const isRecognizing = ref(false)
const isRecording = ref(false)

// 识别结果
const recognitionResult = ref(null)

// 实时文本历史记录
const textHistory = ref([])

// 文本展示区域引用
const textDisplayRef = ref(null)

// 文件上传
const fileInput = ref(null)
const selectedFile = ref(null)

// 麦克风录音（使用自定义录音器）
let audioRecorder = null

// 检查 ASR 状态
const checkStatus = async () => {
  isCheckingStatus.value = true
  
  try {
    const response = await fetch('/api/asr/status')
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    const data = await response.json()
    asrStatus.value = data
    
    console.log('[ASR] Status:', data)
  } catch (error) {
    console.error('[ASR] Failed to check status:', error)
    asrStatus.value = {
      enabled: false,
      message: `检查失败: ${error.message}`
    }
  } finally {
    isCheckingStatus.value = false
  }
}

// 选择文件
const selectFile = () => {
  fileInput.value.click()
}

// 文件改变
const onFileChange = (event) => {
  const file = event.target.files[0]
  if (file) {
    selectedFile.value = file
    console.log('[ASR] File selected:', file.name, file.type, file.size)
  }
}

// 上传并识别
const uploadAndRecognize = async () => {
  if (!selectedFile.value) {
    alert('请先选择音频文件')
    return
  }
  
  isRecognizing.value = true
  recognitionResult.value = null
  
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    
    const response = await fetch('/api/asr/test_upload', {
      method: 'POST',
      body: formData
    })
    
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || '识别失败')
    }
    
    const result = await response.json()
    recognitionResult.value = result
    
    // 添加到历史记录
    if (result.success && result.text) {
      addToHistory(result.text, result)
    }
    
    console.log('[ASR] Recognition result:', result)
  } catch (error) {
    console.error('[ASR] Failed to recognize:', error)
    recognitionResult.value = {
      success: false,
      message: error.message
    }
  } finally {
    isRecognizing.value = false
  }
}

// 添加到历史记录
const addToHistory = (text, metadata = {}) => {
  textHistory.value.push({
    id: Date.now(),
    text,
    timestamp: new Date().toLocaleTimeString('zh-CN'),
    language: metadata.language || '',
    confidence: metadata.confidence || 0,
    duration: metadata.duration || 0
  })
  
  // 滚动到底部
  nextTick(() => {
    if (textDisplayRef.value) {
      textDisplayRef.value.scrollTop = textDisplayRef.value.scrollHeight
    }
  })
}

// 清空历史记录
const clearHistory = () => {
  if (confirm('确定要清空所有识别记录吗？')) {
    textHistory.value = []
    recognitionResult.value = null
  }
}

// 关闭弹窗
const closeModal = () => {
  emit('close')
}

// 开始录音（使用 WAV 格式）
const startRecording = async () => {
  try {
    // 创建录音器（16kHz 采样率，与后端配置一致）
    audioRecorder = new AudioRecorder(16000)
    
    await audioRecorder.start()
    isRecording.value = true
    
    console.log('[ASR] Recording started (WAV format, 16kHz)')
  } catch (error) {
    console.error('[ASR] Failed to start recording:', error)
    alert(`无法访问麦克风: ${error.message}`)
  }
}

// 停止录音
const stopRecording = async () => {
  if (!audioRecorder || !isRecording.value) {
    return
  }
  
  try {
    // 停止录音并获取 WAV Blob
    const wavBlob = await audioRecorder.stop()
    
    // 创建文件对象
    const audioFile = new File([wavBlob], 'recording.wav', { type: 'audio/wav' })
    selectedFile.value = audioFile
    
    console.log(`[ASR] Recording saved: ${audioFile.name}, type: ${audioFile.type}, size: ${audioFile.size} bytes`)
    
    isRecording.value = false
    
    // 自动识别
    await uploadAndRecognize()
  } catch (error) {
    console.error('[ASR] Failed to stop recording:', error)
    isRecording.value = false
  } finally {
    audioRecorder = null
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
    <div class="bg-white rounded-lg shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
      <!-- 标题栏 -->
      <div class="px-6 py-4 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
        <h4 class="font-semibold text-gray-900 flex items-center gap-2">
          <i class="fas fa-microphone text-red-500"></i>
          ASR 测试面板
        </h4>
        <button 
          @click="closeModal"
          class="text-gray-400 hover:text-gray-600 transition-colors"
        >
          <i class="fas fa-times text-xl"></i>
        </button>
      </div>
      
      <!-- 主内容区域 -->
      <div class="flex-1 overflow-hidden flex">
        <!-- 左侧：控制面板 -->
        <div class="w-1/2 border-r border-gray-200 overflow-y-auto p-6 space-y-6">
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
        <div v-if="asrStatus" class="space-y-2">
          <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <span class="text-sm text-gray-600">启用状态</span>
            <span class="px-2 py-1 rounded-full text-xs font-medium"
                  :class="asrStatus.enabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'">
              {{ asrStatus.enabled ? '已启用' : '未启用' }}
            </span>
          </div>
          
          <div v-if="asrStatus.engine" class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <span class="text-sm text-gray-600">引擎</span>
            <span class="text-sm font-medium text-gray-900">{{ asrStatus.engine }}</span>
          </div>
          
          <div v-if="asrStatus.model" class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <span class="text-sm text-gray-600">模型</span>
            <span class="text-sm font-medium text-gray-900">{{ asrStatus.model }}</span>
          </div>
          
          <div v-if="asrStatus.language" class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <span class="text-sm text-gray-600">语言</span>
            <span class="text-sm font-medium text-gray-900">{{ asrStatus.language }}</span>
          </div>
          
          <!-- 模型状态 -->
          <div v-if="asrStatus.models && Object.keys(asrStatus.models).length > 0" class="p-3 bg-gray-50 rounded-lg">
            <div class="text-sm text-gray-600 mb-2">模型状态</div>
            <div class="space-y-1">
              <div v-for="(status, name) in asrStatus.models" :key="name" class="flex items-center justify-between text-xs">
                <span class="text-gray-700">{{ name }}</span>
                <span class="px-2 py-0.5 rounded-full font-medium"
                      :class="status.exists ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-600'">
                  {{ status.exists ? '已安装' : '未安装' }}
                </span>
              </div>
            </div>
          </div>
          
          <!-- 消息提示 -->
          <div v-if="asrStatus.message" 
               class="p-3 rounded-lg"
               :class="asrStatus.enabled ? 'bg-green-50 text-green-700' : 'bg-yellow-50 text-yellow-700'">
            <p class="text-sm">{{ asrStatus.message }}</p>
          </div>
        </div>
        
        <!-- 加载中 -->
        <div v-else class="flex items-center justify-center py-8 text-gray-400">
          <i class="fas fa-spinner fa-spin text-2xl"></i>
        </div>
      </div>
      
      <!-- 文件上传测试 -->
      <div class="pt-6 border-t border-gray-200">
        <h5 class="text-sm font-semibold text-gray-700 mb-3">文件上传测试</h5>
        
        <div class="space-y-3">
          <!-- 文件选择 -->
          <div>
            <input 
              ref="fileInput"
              type="file"
              accept="audio/wav,audio/x-wav,audio/wave,audio/mpeg,audio/mp3,audio/x-m4a,audio/mp4"
              @change="onFileChange"
              class="hidden"
            />
            
            <button 
              @click="selectFile"
              class="w-full px-4 py-3 border-2 border-dashed border-gray-300 rounded-lg hover:border-blue-400 hover:bg-blue-50 transition-colors flex items-center justify-center gap-2 text-gray-600 hover:text-blue-600"
            >
              <i class="fas fa-upload"></i>
              {{ selectedFile ? selectedFile.name : '选择音频文件' }}
            </button>
            
            <p class="text-xs text-gray-500 mt-1">推荐 WAV 格式（16kHz, 单声道），也支持 MP3, M4A, MP4</p>
          </div>
          
          <!-- 识别按钮 -->
          <button 
            @click="uploadAndRecognize"
            :disabled="!selectedFile || isRecognizing || !asrStatus?.enabled"
            class="w-full px-4 py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            <i class="fas" :class="isRecognizing ? 'fa-spinner fa-spin' : 'fa-play'"></i>
            {{ isRecognizing ? '识别中...' : '开始识别' }}
          </button>
        </div>
      </div>
      
      <!-- 麦克风录音测试 -->
      <div class="pt-6 border-t border-gray-200">
        <h5 class="text-sm font-semibold text-gray-700 mb-3">麦克风录音测试</h5>
        
        <div class="space-y-3">
          <button 
            v-if="!isRecording"
            @click="startRecording"
            :disabled="!asrStatus?.enabled"
            class="w-full px-4 py-3 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            <i class="fas fa-microphone"></i>
            开始录音
          </button>
          
          <button 
            v-else
            @click="stopRecording"
            class="w-full px-4 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors flex items-center justify-center gap-2 animate-pulse"
          >
            <i class="fas fa-stop"></i>
            停止录音
          </button>
          
          <p class="text-xs text-gray-500 text-center">录音格式：WAV (16kHz, 单声道)，停止后自动识别</p>
        </div>
      </div>
      
      <!-- 识别结果 -->
      <div v-if="recognitionResult" class="pt-6 border-t border-gray-200">
        <h5 class="text-sm font-semibold text-gray-700 mb-3">识别结果</h5>
        
        <div v-if="recognitionResult.success" class="space-y-3">
          <!-- 识别文本 -->
          <div class="p-4 bg-green-50 border border-green-200 rounded-lg">
            <div class="text-xs text-green-600 mb-1">识别文本</div>
            <div class="text-base text-green-900 font-medium">{{ recognitionResult.text }}</div>
          </div>
          
          <!-- 详细信息 -->
          <div class="grid grid-cols-2 gap-2">
            <div v-if="recognitionResult.language" class="p-3 bg-gray-50 rounded-lg">
              <div class="text-xs text-gray-500">语言</div>
              <div class="text-sm font-medium text-gray-900">{{ recognitionResult.language }}</div>
            </div>
            
            <div v-if="recognitionResult.confidence" class="p-3 bg-gray-50 rounded-lg">
              <div class="text-xs text-gray-500">置信度</div>
              <div class="text-sm font-medium text-gray-900">{{ (recognitionResult.confidence * 100).toFixed(1) }}%</div>
            </div>
            
            <div v-if="recognitionResult.duration" class="p-3 bg-gray-50 rounded-lg">
              <div class="text-xs text-gray-500">时长</div>
              <div class="text-sm font-medium text-gray-900">{{ recognitionResult.duration.toFixed(2) }}s</div>
            </div>
          </div>
        </div>
        
        <!-- 失败提示 -->
        <div v-else class="p-4 bg-red-50 border border-red-200 rounded-lg">
          <div class="text-sm text-red-700">
            <i class="fas fa-exclamation-circle mr-2"></i>
            {{ recognitionResult.message || '识别失败' }}
          </div>
        </div>
      </div>
      
      <!-- 提示信息 -->
      <div v-if="!asrStatus?.enabled" class="p-3 bg-yellow-50 text-yellow-700 rounded-lg">
        <p class="text-sm">
          <i class="fas fa-exclamation-triangle mr-2"></i>
          ASR 服务未启用，请在配置中启用 ASR 功能
        </p>
      </div>
        </div>
        
        <!-- 右侧：实时文本展示 -->
        <div class="w-1/2 flex flex-col">
          <!-- 标题栏 -->
          <div class="px-6 py-4 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
            <h5 class="text-sm font-semibold text-gray-700 flex items-center gap-2">
              <i class="fas fa-comment-dots text-blue-500"></i>
              实时识别文本
            </h5>
            <button 
              v-if="textHistory.length > 0"
              @click="clearHistory"
              class="px-3 py-1.5 text-xs bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors flex items-center gap-1"
            >
              <i class="fas fa-trash"></i>
              清空
            </button>
          </div>
          
          <!-- 文本展示区域 -->
          <div 
            ref="textDisplayRef"
            class="flex-1 overflow-y-auto p-6 bg-gray-50"
          >
            <!-- 空状态 -->
            <div v-if="textHistory.length === 0" class="h-full flex flex-col items-center justify-center text-gray-400">
              <i class="fas fa-microphone-slash text-5xl mb-4"></i>
              <p class="text-sm">暂无识别记录</p>
              <p class="text-xs mt-1">上传音频或录音后，识别结果将显示在这里</p>
            </div>
            
            <!-- 历史记录 -->
            <div v-else class="space-y-4">
              <div 
                v-for="item in textHistory" 
                :key="item.id"
                class="bg-white rounded-lg border border-gray-200 shadow-sm p-4 hover:shadow-md transition-shadow"
              >
                <!-- 时间戳 -->
                <div class="flex items-center justify-between mb-2">
                  <span class="text-xs text-gray-500">
                    <i class="fas fa-clock mr-1"></i>
                    {{ item.timestamp }}
                  </span>
                  <div class="flex items-center gap-2">
                    <span v-if="item.language" class="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded">
                      {{ item.language }}
                    </span>
                    <span v-if="item.confidence > 0" class="text-xs px-2 py-0.5 bg-green-100 text-green-700 rounded">
                      {{ (item.confidence * 100).toFixed(0) }}%
                    </span>
                  </div>
                </div>
                
                <!-- 识别文本 -->
                <div class="text-gray-900 leading-relaxed">
                  {{ item.text }}
                </div>
                
                <!-- 音频时长 -->
                <div v-if="item.duration > 0" class="mt-2 text-xs text-gray-500">
                  <i class="fas fa-stopwatch mr-1"></i>
                  时长: {{ item.duration.toFixed(2) }}s
                </div>
              </div>
            </div>
          </div>
          
          <!-- 当前识别状态 -->
          <div v-if="isRecognizing || isRecording" class="px-6 py-3 border-t border-gray-200 bg-blue-50">
            <div class="flex items-center gap-2 text-blue-700">
              <i class="fas fa-spinner fa-spin"></i>
              <span class="text-sm font-medium">
                {{ isRecording ? '正在录音...' : '正在识别...' }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
