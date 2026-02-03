<script setup>
/**
 * 聊天输入框组件 (Presentational Component)
 * =========================================================================
 * 
 * 【组件类型】Dumb Component（纯展示组件）
 * 【职责】
 * - 提供用户输入界面
 * - 显示多媒体功能按钮（图片、语音、文件）
 * - 显示发送和停止按钮
 * - 根据状态控制按钮的可用性
 * 
 * 【设计原则】
 * - 不包含业务逻辑，只负责 UI 展示和交互
 * - 使用 v-model 双向绑定输入内容
 * - 所有操作通过事件通知父组件
 * 
 * 【Props】
 * @prop {string} modelValue - 输入框内容（v-model 绑定）
 * @prop {boolean} isConnected - WebSocket 连接状态
 * @prop {boolean} isRecording - 是否正在录音
 * @prop {string} backendState - 后端处理状态（idle/thinking/speaking）
 * @prop {boolean} isTyping - AI 是否正在输入
 * 
 * 【Events】
 * @event update:modelValue - 输入内容变化（v-model）
 * @event send - 发送消息
 * @event toggle-recording - 切换录音状态
 * @event stop-interaction - 停止当前交互（打断 AI 回复）
 * 
 * 【交互逻辑】
 * - Enter 键发送消息
 * - 连接断开或内容为空时禁用发送按钮
 * - AI 回复中显示停止按钮
 * - 录音中显示录音状态动画
 */

// ========================================================================
// Props 定义
// ========================================================================

const props = defineProps({
  /** 输入框内容（v-model 绑定） */
  modelValue: {
    type: String,
    default: ''
  },
  
  /** WebSocket 连接状态 */
  isConnected: {
    type: Boolean,
    required: true
  },
  
  /** 是否正在录音 */
  isRecording: {
    type: Boolean,
    default: false
  },
  
  /** 后端处理状态：idle（空闲）/ thinking（思考中）/ speaking（回复中） */
  backendState: {
    type: String,
    default: 'idle'
  },
  
  /** AI 是否正在输入（流式输出中） */
  isTyping: {
    type: Boolean,
    default: false
  }
})

// ========================================================================
// Events 定义
// ========================================================================

const emit = defineEmits([
  'update:modelValue',   // v-model 更新
  'send',                // 发送消息
  'toggle-recording',    // 切换录音
  'stop-interaction'     // 停止交互
])

// ========================================================================
// 方法
// ========================================================================

/**
 * 处理输入事件
 * 
 * 【功能】实现 v-model 双向绑定
 * @param {Event} event - input 事件对象
 */
const handleInput = (event) => {
  emit('update:modelValue', event.target.value)
}

/**
 * 处理发送消息
 * 
 * 【功能】验证并发送消息
 * 【验证规则】
 * - 内容不能为空（去除首尾空格）
 * - WebSocket 必须已连接
 * 
 * 【调用时机】
 * - 用户点击发送按钮
 * - 用户按下 Enter 键
 */
const handleSend = () => {
  if (props.modelValue.trim() && props.isConnected) {
    emit('send')
  }
}
</script>

<template>
  <div class="p-4 md:p-6 bg-white border-t border-gray-100">
    <div class="max-w-4xl mx-auto">
      <!-- 输入框容器 -->
      <div class="relative bg-gray-50 border border-gray-200 rounded-2xl p-2 focus-within:ring-2 focus-within:ring-blue-100 focus-within:border-blue-400 transition-all shadow-sm">
        <!-- 文本域: 支持多行输入 -->
        <textarea 
          :value="modelValue"
          @input="handleInput"
          @keydown.enter.prevent="handleSend"
          placeholder="发送消息给 AI..." 
          class="w-full bg-transparent border-none focus:ring-0 resize-none max-h-32 min-h-[44px] py-2 px-3 text-gray-800 placeholder-gray-400"
          rows="1"
        ></textarea>
        
        <!-- 底部工具栏与发送按钮 -->
        <div class="flex items-center justify-between px-2 pb-1">
          <div class="flex items-center gap-2">
             <!-- 多媒体按钮组 -->
             <button class="p-2 text-gray-400 hover:text-blue-500 hover:bg-blue-50 rounded-full transition-colors" title="Upload Image">
              <i class="fas fa-image"></i>
            </button>
            <button 
              @click="emit('toggle-recording')"
              class="p-2 rounded-full transition-colors relative"
              :class="isRecording ? 'text-red-500 bg-red-50' : 'text-gray-400 hover:text-green-500 hover:bg-green-50'"
              title="Voice Input"
            >
              <i class="fas" :class="isRecording ? 'fa-stop' : 'fa-microphone'"></i>
              <span v-if="isRecording" class="absolute inset-0 rounded-full border border-red-400 opacity-75 animate-ping"></span>
            </button>
            <button class="p-2 text-gray-400 hover:text-orange-500 hover:bg-orange-50 rounded-full transition-colors" title="Attach File">
              <i class="fas fa-paperclip"></i>
            </button>
          </div>
          
          <!-- 发送按钮与停止按钮 -->
          <div class="flex items-center gap-2">
            <!-- 停止按钮 (仅在非空闲状态下显示) -->
            <button 
              v-if="backendState === 'speaking' || backendState === 'thinking' || isTyping"
              @click="emit('stop-interaction')"
              class="w-10 h-10 rounded-full flex items-center justify-center transition-all duration-200 shadow-md bg-red-50 text-red-500 hover:bg-red-500 hover:text-white border border-red-200 animate-pulse"
              title="Stop / Interrupt"
            >
              <i class="fas fa-stop text-sm"></i>
            </button>

            <!-- 发送按钮 -->
            <button 
              @click="handleSend"
              :disabled="!modelValue.trim() || !isConnected"
              :class="{'opacity-50 cursor-not-allowed': !modelValue.trim() || !isConnected, 'hover:bg-blue-600 hover:shadow-lg': modelValue.trim() && isConnected}"
              class="bg-blue-500 text-white w-10 h-10 rounded-full flex items-center justify-center transition-all duration-200 shadow-md"
            >
              <i class="fas fa-paper-plane text-sm"></i>
            </button>
          </div>
        </div>
      </div>
      
      <!-- 免责声明 -->
      <div class="text-center mt-3">
        <p class="text-xs text-gray-400">AI output may be inaccurate. Please verify important information.</p>
      </div>
    </div>
  </div>
</template>
