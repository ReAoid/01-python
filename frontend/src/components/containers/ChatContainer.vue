<script setup>
/**
 * 聊天容器组件 (Container/Smart Component)
 * =========================================================================
 * 
 * 【组件类型】Smart Component（智能组件）
 * 【职责】
 * - 管理聊天相关的业务逻辑
 * - 协调 WebSocket 通信
 * - 处理音频输入输出（TTS/ASR）
 * - 管理聊天状态和配置
 * - 协调多个 Presentational 组件
 * 
 * 【设计模式】Container/Presentational 模式
 * - 本组件作为 Container 负责逻辑和数据
 * - 使用 Composables 封装复用逻辑
 * - 将 UI 渲染委托给 Presentational 组件
 * 
 * 【依赖的 Composables】
 * - useChat: 聊天消息管理
 * - useWebSocket: WebSocket 连接管理
 * 
 * 【管理的功能】
 * - 文本聊天（用户输入 → AI 流式回复）
 * - 语音输入（ASR：语音转文字）
 * - 语音输出（TTS：文字转语音）
 * - 打断机制（停止 AI 回复）
 * - 热重载（重置会话状态）
 * 
 * 【Props】
 * @prop {boolean} showSidebar - 侧边栏显示状态
 * 
 * 【Events】
 * @event toggle-sidebar - 切换侧边栏
 * @event log-entry - 转发后端日志到父组件
 * @event connection-change - WebSocket 连接状态变化
 */

import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useChat } from '../../composables/useChat'
import { useWebSocket } from '../../composables/useWebSocket'
import { AudioManager } from '../../utils/audio.js'
import ChatHeader from '../presentational/ChatHeader.vue'
import ChatMessages from '../presentational/ChatMessages.vue'
import ChatInput from '../presentational/ChatInput.vue'

// ========================================================================
// Props & Events
// ========================================================================

const props = defineProps({
  /** 侧边栏是否显示 */
  showSidebar: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits([
  'toggle-sidebar',       // 切换侧边栏
  'log-entry',            // 转发日志
  'connection-change'     // 连接状态变化
])

// ========================================================================
// Composables & 工具类
// ========================================================================

/** 聊天功能 Composable */
const chat = useChat()

/** WebSocket 连接 Composable */
const ws = useWebSocket()

/** 音频管理器（处理 TTS 播放和 ASR 录音） */
const audioManager = new AudioManager()

// ========================================================================
// 状态管理
// ========================================================================

/** 是否启用 TTS 语音播放模式 */
const isVoiceMode = ref(false)

/** 是否启用 ASR 语音输入模式（实时语音转文字） */
const isASRMode = ref(false)

/** 是否正在录音（手动录音按钮） */
const isRecording = ref(false)

/** 是否被打断（用户点击停止） */
const isInterrupted = ref(false)

/** 后端处理状态：idle（空闲）/ thinking（思考中）/ speaking（回复中） */
const backendState = ref('idle')

// ========================================================================
// 配置管理
// ========================================================================

/**
 * 获取页面配置
 * 
 * 【功能】从后端加载页面级配置
 * 【API】GET /api/config/page_config
 * 
 * 【配置项】
 * - character_name: AI 角色名称
 * - first_message: 初始欢迎消息
 * 
 * 【调用时机】组件挂载时
 */
const fetchPageConfig = async () => {
  try {
    const response = await fetch('/api/config/page_config')
    if (response.ok) {
      const data = await response.json()
      if (data.character_name) chat.characterName.value = data.character_name
      if (data.first_message) {
        chat.initialMessage.value = data.first_message
        // 更新已显示的初始消息
        if (chat.messages.value.length === 1 && chat.messages.value[0].role === 'ai') {
          chat.messages.value[0].content = data.first_message
        }
      }
      console.log('[Config] Loaded page config:', data)
    }
  } catch (err) {
    console.error('[Config] Failed to fetch page config:', err)
  }
}

/**
 * 发送配置到后端
 * 
 * 【功能】同步前端的输入/输出模式配置到后端
 * 【WebSocket 消息类型】config
 * 
 * 【配置项】
 * - input_mode: "text" | "realtime_audio"（ASR 模式）
 * - output_mode: "text_only" | "text_audio"（TTS 模式）
 * 
 * 【调用时机】
 * - WebSocket 连接成功后
 * - 切换 TTS/ASR 模式时
 */
const sendConfig = () => {
  if (!ws.isConnected.value) return
  
  const configData = {
    input_mode: isASRMode.value ? "realtime_audio" : "text",
    output_mode: isVoiceMode.value ? "text_audio" : "text_only"
  }

  console.log('[Config] Sending config update:', configData)
  
  ws.send({
    type: "config",
    data: configData
  })
}

// ========================================================================
// 模式切换
// ========================================================================

/**
 * 切换 TTS 语音播放模式
 * 
 * 【功能】启用/禁用 AI 回复的语音播放
 * 【影响】
 * - 开启：AI 回复会同时输出文字和语音
 * - 关闭：AI 回复只输出文字
 */
const toggleVoiceMode = () => {
  isVoiceMode.value = !isVoiceMode.value
  console.log('[UI] Voice Mode toggled:', isVoiceMode.value ? 'ON' : 'OFF')
  sendConfig()
}

/**
 * 切换 ASR 语音输入模式
 * 
 * 【功能】启用/禁用实时语音转文字
 * 【流程】
 * - 开启：请求麦克风权限 → 开始录音 → 实时发送音频数据
 * - 关闭：停止录音
 * 
 * 【权限】需要浏览器麦克风权限
 * 【错误处理】权限拒绝时显示提示
 */
const toggleASRMode = async () => {
  if (isASRMode.value) {
    // 关闭 ASR 模式
    audioManager.stopRecording()
    isASRMode.value = false
    console.log('[UI] ASR Mode disabled')
  } else {
    // 开启 ASR 模式
    try {
      await audioManager.startRecording((pcmData) => {
        if (ws.isConnected.value) {
          ws.sendBinary(pcmData)  // 实时发送音频数据
        }
      })
      isASRMode.value = true
      console.log('[UI] ASR Mode enabled')
    } catch (e) {
      console.error('[UI] Failed to start ASR mode:', e)
      alert('无法访问麦克风，请检查权限设置')
      return
    }
  }
  sendConfig()
}

/**
 * 切换手动录音状态
 * 
 * 【功能】点击麦克风按钮进行录音
 * 【区别】与 ASR 模式不同，这是临时录音
 * 
 * 【流程】
 * - 开始录音 → 实时发送音频数据
 * - 停止录音 → 结束本次录音
 */
const toggleRecording = async () => {
  if (isRecording.value) {
    audioManager.stopRecording()
    isRecording.value = false
  } else {
    try {
      await audioManager.startRecording((pcmData) => {
        if (ws.isConnected.value) {
          ws.sendBinary(pcmData)
        }
      })
      isRecording.value = true
      sendConfig()
    } catch (e) {
      console.error('[UI] Start recording failed:', e)
      alert('无法访问麦克风')
    }
  }
}

// ========================================================================
// 交互控制
// ========================================================================

/**
 * 停止当前交互
 * 
 * 【功能】打断 AI 的回复
 * 【操作】
 * - 停止音频播放
 * - 发送打断信号到后端
 * - 重置输入状态
 * 
 * 【使用场景】
 * - AI 回复内容不满意，想重新提问
 * - AI 回复太长，想打断
 */
const stopInteraction = () => {
  isInterrupted.value = true
  audioManager.stopPlayback()
  
  if (ws.isConnected.value) {
    ws.send({
      type: "interrupt"
    })
  }
  
  chat.isTyping.value = false
  isRecording.value = false
  console.log('[UI] Interaction stopped')
}

/**
 * 执行热重载
 * 
 * 【功能】重置整个会话状态
 * 【操作】
 * - 清空所有消息
 * - 重置所有状态
 * - 停止音频播放和录音
 * - 通知后端重新加载
 * 
 * 【使用场景】
 * - 修改了后端代码，需要重新加载
 * - 重置会话，从头开始
 */
const performHotReload = () => {
  if (!ws.isConnected.value) {
    alert('未连接到服务器，无法执行热更新')
    return
  }

  // 重置所有状态
  chat.clearMessages()
  chat.isTyping.value = false
  isRecording.value = false
  isInterrupted.value = false
  chat.userInput.value = ''
  audioManager.stopPlayback()

  // 通知后端
  ws.send({
    type: "hot_reload"
  })

  console.log('[UI] Hot reload triggered')
}

// ========================================================================
// 消息处理
// ========================================================================

/**
 * 发送文本消息
 * 
 * 【功能】将用户输入发送到后端
 * 【流程】
 * 1. 验证输入（非空 + 已连接）
 * 2. 添加用户消息到列表
 * 3. 清空输入框
 * 4. 通过 WebSocket 发送
 * 5. 开始等待 AI 回复
 * 
 * 【WebSocket 消息】type: "user_text"
 */
const sendMessage = () => {
  if (!chat.userInput.value.trim() || !ws.isConnected.value) return

  const content = chat.userInput.value
  isInterrupted.value = false

  // 添加用户消息到界面
  chat.addUserMessage(content)
  
  // 标记上一条 AI 消息为已完成（防止流式追加）
  const lastMessage = chat.messages.value[chat.messages.value.length - 2]
  if (lastMessage && lastMessage.role === 'ai') {
    lastMessage.isComplete = true
  }

  // 清空输入框并准备接收回复
  chat.userInput.value = ''
  chat.scrollToBottom()
  chat.isTyping.value = true
  
  // 发送到后端
  ws.send({
    type: "user_text",
    content: content
  })
}

/**
 * 处理 WebSocket 接收的消息
 * 
 * @param {Object} message - WebSocket 消息对象
 * 
 * 【支持的消息类型】
 * - text_stream: AI 流式回复的文本片段
 * - user_message: 用户消息（ASR 转写结果）
 * - state_change: 后端状态变化
 * - log_entry: 后端日志条目
 * 
 * 【流式输出】
 * - AI 回复采用流式传输，每次收到一小段文本
 * - 自动追加到最后一条 AI 消息上
 */
const handleSocketMessage = (message) => {
  if (message.type === 'text_stream') {
    // AI 流式回复
    chat.isTyping.value = false
    chat.addOrUpdateAIMessage(message.content)
    chat.scrollToBottom()
  } else if (message.type === 'user_message') {
    // ASR 转写的用户消息
    chat.addUserMessage(message.content)
    
    // 标记上一条 AI 消息为已完成
    const prevMessage = chat.messages.value[chat.messages.value.length - 2]
    if (prevMessage && prevMessage.role === 'ai') {
      prevMessage.isComplete = true
    }
    
    chat.scrollToBottom()
    console.log('[ASR] User message displayed:', message.content)
  } else if (message.type === 'state_change') {
    // 后端状态变化
    console.log('[Backend] State changed:', message.state)
    backendState.value = message.state
    
    if (message.state === 'idle' || message.state === 'interrupted') {
      chat.isTyping.value = false
    }
  } else if (message.type === 'log_entry') {
    // 转发日志给父组件处理
    emit('log-entry', message.data)
  }
}

/**
 * 处理音频数据
 * 
 * @param {ArrayBuffer} arrayBuffer - PCM 音频数据
 * 
 * 【功能】接收并播放 TTS 生成的音频
 * 【格式】PCM 16位 16kHz 单声道
 * 【打断】如果用户点击了停止，忽略后续音频
 */
const handleAudioData = (arrayBuffer) => {
  if (isInterrupted.value) return  // 已被打断，忽略音频
  
  if (arrayBuffer.byteLength > 0) {
    audioManager.playPCM(arrayBuffer)
  }
}

// ========================================================================
// 生命周期
// ========================================================================

/**
 * 组件挂载
 * 
 * 【初始化流程】
 * 1. 初始化消息列表（显示欢迎消息）
 * 2. 加载页面配置（角色名称等）
 * 3. 建立 WebSocket 连接
 * 4. 监听连接状态，连接成功后发送配置
 */
onMounted(() => {
  chat.initMessages()
  fetchPageConfig()
  ws.connect(handleSocketMessage, handleAudioData)
  
  // 【重要】WebSocket 连接成功后立即发送配置
  watch(() => ws.isConnected.value, (connected) => {
    if (connected) {
      sendConfig()
      // 通知父组件连接状态变化
      emit('connection-change', connected)
    }
  })
})

/**
 * 组件卸载
 * 
 * 【清理工作】
 * - 断开 WebSocket 连接
 * - 停止音频播放
 * - 停止录音
 * - 防止内存泄漏
 */
onUnmounted(() => {
  ws.disconnect()
  audioManager.stopPlayback()
  audioManager.stopRecording()
})
</script>

<template>
  <div class="flex-1 flex flex-col h-full">
    <!-- 头部 -->
    <ChatHeader
      :character-name="chat.characterName.value"
      :is-connected="ws.isConnected.value"
      :backend-state="backendState"
      :is-voice-mode="isVoiceMode"
      :is-asr-mode="isASRMode"
      :is-typing="chat.isTyping.value"
      :show-sidebar="showSidebar"
      @toggle-sidebar="emit('toggle-sidebar')"
      @toggle-voice-mode="toggleVoiceMode"
      @toggle-asr-mode="toggleASRMode"
      @hot-reload="performHotReload"
    />

    <!-- 消息列表 -->
    <ChatMessages
      ref="chat.chatContainer"
      :messages="chat.messages.value"
      :is-typing="chat.isTyping.value"
    />

    <!-- 输入框 -->
    <ChatInput
      v-model="chat.userInput.value"
      :is-connected="ws.isConnected.value"
      :is-recording="isRecording"
      :backend-state="backendState"
      :is-typing="chat.isTyping.value"
      @send="sendMessage"
      @toggle-recording="toggleRecording"
      @stop-interaction="stopInteraction"
    />
  </div>
</template>
