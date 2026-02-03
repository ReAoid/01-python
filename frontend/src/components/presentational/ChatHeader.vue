<script setup>
/**
 * 聊天头部组件 (Presentational Component)
 * =========================================================================
 * 
 * 【组件类型】Dumb Component（纯展示组件）
 * 【职责】
 * - 显示 AI 角色信息和头像
 * - 显示 WebSocket 连接状态
 * - 显示后端处理状态（空闲/思考中/回复中）
 * - 提供功能控制按钮（TTS/ASR/热重载）
 * 
 * 【设计原则】
 * - 不包含业务逻辑，只负责展示
 * - 所有数据通过 props 接收
 * - 所有交互通过 emit 事件通知父组件
 * 
 * 【Props】
 * @prop {string} characterName - AI 角色名称
 * @prop {boolean} isConnected - WebSocket 连接状态
 * @prop {string} backendState - 后端状态（idle/thinking/speaking）
 * @prop {boolean} isVoiceMode - 是否启用 TTS 语音模式
 * @prop {boolean} isASRMode - 是否启用 ASR 语音输入模式
 * @prop {boolean} isTyping - AI 是否正在输入
 * @prop {boolean} showSidebar - 侧边栏是否显示
 * 
 * 【Events】
 * @event toggle-sidebar - 切换侧边栏显示/隐藏
 * @event toggle-voice-mode - 切换 TTS 语音模式
 * @event toggle-asr-mode - 切换 ASR 语音输入模式
 * @event hot-reload - 触发后端热重载
 */

// ========================================================================
// Props 定义
// ========================================================================

const props = defineProps({
  /** AI 角色名称 */
  characterName: {
    type: String,
    required: true
  },
  
  /** WebSocket 连接状态 */
  isConnected: {
    type: Boolean,
    required: true
  },
  
  /** 后端处理状态：idle（空闲）/ thinking（思考中）/ speaking（回复中） */
  backendState: {
    type: String,
    default: 'idle'
  },
  
  /** 是否启用 TTS 语音播放模式 */
  isVoiceMode: {
    type: Boolean,
    default: false
  },
  
  /** 是否启用 ASR 语音输入模式 */
  isASRMode: {
    type: Boolean,
    default: false
  },
  
  /** AI 是否正在输入（流式输出中） */
  isTyping: {
    type: Boolean,
    default: false
  },
  
  /** 侧边栏是否显示（移动端控制） */
  showSidebar: {
    type: Boolean,
    default: true
  }
})

// ========================================================================
// Events 定义
// ========================================================================

const emit = defineEmits([
  'toggle-sidebar',     // 切换侧边栏
  'toggle-voice-mode',  // 切换 TTS
  'toggle-asr-mode',    // 切换 ASR
  'hot-reload'          // 热重载
])
</script>

<template>
  <div class="h-16 px-6 bg-white border-b border-gray-100 flex items-center justify-between z-10">
    <div class="flex items-center gap-4">
      <!-- 移动端侧边栏切换按钮 -->
      <button @click="emit('toggle-sidebar')" class="p-2 text-gray-500 hover:bg-gray-100 rounded-lg md:hidden">
        <i class="fas fa-bars"></i>
      </button>
      
      <!-- AI 助手信息展示 -->
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center text-blue-600">
          <i class="fas fa-robot text-lg"></i>
        </div>
        <div>
          <h1 class="font-bold text-gray-900 text-lg leading-tight">{{ characterName }}</h1>
          <div class="flex items-center gap-2">
            <span class="w-2 h-2 rounded-full" :class="isConnected ? 'bg-green-500' : 'bg-red-500'"></span>
            <span class="text-xs text-gray-500">{{ isConnected ? 'Online' : 'Offline' }}</span>
            <!-- 状态可视化标签 -->
            <span v-if="backendState !== 'idle'" 
                  class="ml-2 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider rounded-full"
                  :class="{
                      'bg-yellow-100 text-yellow-700': backendState === 'thinking',
                      'bg-green-100 text-green-700': backendState === 'speaking',
                      'bg-red-100 text-red-700': backendState === 'interrupted'
                  }">
                {{ backendState }}
            </span>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 右侧工具栏按钮 -->
    <div class="flex items-center gap-3">
      <!-- TTS语音输出开关 -->
      <button 
        @click="emit('toggle-voice-mode')" 
        class="px-3 py-1.5 rounded-full text-xs font-medium transition-colors border flex items-center gap-2"
        :class="isVoiceMode ? 'bg-blue-50 text-blue-600 border-blue-200' : 'bg-gray-50 text-gray-500 border-gray-200'"
        title="切换语音输出 (TTS)"
      >
        <i class="fas" :class="isVoiceMode ? 'fa-volume-up' : 'fa-volume-mute'"></i>
        <span class="hidden md:inline">{{ isVoiceMode ? 'TTS On' : 'TTS Off' }}</span>
      </button>

      <!-- ASR持续录音开关 -->
      <button 
        @click="emit('toggle-asr-mode')" 
        class="px-3 py-1.5 rounded-full text-xs font-medium transition-colors border flex items-center gap-2 relative"
        :class="isASRMode ? 'bg-red-50 text-red-600 border-red-200' : 'bg-gray-50 text-gray-500 border-gray-200'"
        title="切换语音输入 (ASR持续录音)"
      >
        <i class="fas" :class="isASRMode ? 'fa-microphone' : 'fa-microphone-slash'"></i>
        <span class="hidden md:inline">{{ isASRMode ? 'ASR On' : 'ASR Off' }}</span>
        <!-- 录音中的动画指示器 -->
        <span v-if="isASRMode" class="absolute -top-1 -right-1 w-3 h-3 bg-red-500 rounded-full animate-pulse"></span>
      </button>

      <!-- 主动热更新按钮 -->
      <button 
        @click="emit('hot-reload')"
        :disabled="backendState === 'thinking' || backendState === 'speaking' || isTyping"
        :class="{
          'opacity-50 cursor-not-allowed': backendState === 'thinking' || backendState === 'speaking' || isTyping,
          'hover:bg-green-100 hover:text-green-600': backendState === 'idle' && !isTyping
        }"
        class="w-9 h-9 flex items-center justify-center rounded-full text-gray-500 transition-colors border border-gray-200"
        title="Hot Reload - 清空会话并重新开始（不包含历史总结）"
      >
        <i class="fas fa-sync"></i>
      </button>
    </div>
  </div>
</template>
