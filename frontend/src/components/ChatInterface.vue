<script setup>
/**
 * 聊天主界面组件 (Chat Interface)
 * -------------------------------------------------------------------------
 * 这是一个功能完整的聊天窗口组件，实现了消息流展示、用户输入、侧边栏交互等功能。
 * 
 * 主要功能:
 * 1. 消息列表管理 (Messages State): 存储和展示对话历史。
 * 2. 真实 AI 交互: 通过 WebSocket 与后端通信。
 * 3. 自动滚动 (Auto-scroll): 新消息到来时自动滚动到底部。
 * 4. 响应式侧边栏 (Responsive Sidebar): 在移动端支持抽屉式切换。
 */

import { ref, computed, nextTick, onMounted, onUnmounted, watch } from 'vue'
import MessageBubble from './MessageBubble.vue'
import Sidebar from './Sidebar.vue'
import { AudioManager } from '../utils/audio.js'

// =========================================================================
// 1. 状态定义 (State Definitions)
// =========================================================================

const audioManager = new AudioManager()

// 角色名称
const characterName = ref('灵依')

// 初始欢迎消息
const initialMessage = ref('你好！我是你的私人AI助手。有什么我可以帮你的吗？')

/**
 * 消息列表数据
 * id: 唯一标识
 * role: 'user' (用户) | 'ai' (机器人)
 * content: 消息文本内容
 * timestamp: 发送时间
 * type: 消息类型 (目前仅支持 'text')
 */
const messages = ref([
  {
    id: 1,
    role: 'ai',
    content: initialMessage.value,
    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    type: 'text'
  }
])

// 用户当前输入的文本
const userInput = ref('')

// AI 是否正在输入 (用于控制 Loading 动画显示)
const isTyping = ref(false)

// 聊天区域的 DOM 引用 (用于实现自动滚动)
const chatContainer = ref(null)

// 侧边栏显示状态 (桌面端默认显示,移动端默认隐藏)
const showSidebar = ref(true)

// 当前激活的标签页
const activeTab = ref('chat')

// WebSocket 连接实例
const socket = ref(null)
const isConnected = ref(false)
const reconnectInterval = ref(null)

// 语音相关状态
const isVoiceMode = ref(false) // 是否开启语音回复 (TTS)
const isRecording = ref(false) // 是否正在录音

// 交互控制
const isInterrupted = ref(false) // 是否处于打断状态 (用于丢弃滞后的音频包)

// 后端状态
// idle, thinking, speaking, interrupted
// idle=空闲，thinking=思考中，speaking=说话中，interrupted=被打断
const backendState = ref('idle') 

// 快捷操作按钮配置 (暂未启用，预留功能)
const quickActions = [
  { icon: 'fas fa-image', label: '图片', color: 'text-blue-500' },
  { icon: 'fas fa-microphone', label: '语音', color: 'text-green-500' },
  { icon: 'fas fa-file-alt', label: '文档', color: 'text-orange-500' }
]

// =========================================================================
// 日志系统状态 (Log System State)
// =========================================================================

// 日志级别配置
const LOG_LEVELS = {
  DEBUG: { label: 'DEBUG', color: 'text-gray-500', bg: 'bg-gray-50', icon: 'fa-bug' },
  INFO: { label: 'INFO', color: 'text-blue-600', bg: 'bg-blue-50', icon: 'fa-info-circle' },
  SUCCESS: { label: 'SUCCESS', color: 'text-green-600', bg: 'bg-green-50', icon: 'fa-check-circle' },
  WARNING: { label: 'WARNING', color: 'text-yellow-600', bg: 'bg-yellow-50', icon: 'fa-exclamation-triangle' },
  ERROR: { label: 'ERROR', color: 'text-red-600', bg: 'bg-red-50', icon: 'fa-times-circle' }
}

// 日志存储 (环形缓冲区，最多1000条)
const logs = ref([])
const MAX_LOGS = 1000

// 日志过滤状态
const logFilters = ref({
  levels: ['INFO', 'SUCCESS', 'WARNING', 'ERROR'], // 默认不显示 DEBUG
  search: ''
})

// 日志控制状态
const logPaused = ref(false)
const showLevelFilter = ref(false)
const logContainer = ref(null)
const isLogScrollAtBottom = ref(true)

// 日志统计
const logStats = computed(() => ({
  total: logs.value.length,
  error: logs.value.filter(l => l.level === 'ERROR').length,
  warning: logs.value.filter(l => l.level === 'WARNING').length,
  info: logs.value.filter(l => l.level === 'INFO' || l.level === 'SUCCESS').length
}))

// 过滤后的日志
const filteredLogs = computed(() => {
  return logs.value.filter(log => {
    // 级别过滤
    if (!logFilters.value.levels.includes(log.level)) return false
    
    // 搜索关键词
    if (logFilters.value.search) {
      const searchLower = logFilters.value.search.toLowerCase()
      return (
        log.message?.toLowerCase().includes(searchLower) ||
        log.module?.toLowerCase().includes(searchLower) ||
        log.function?.toLowerCase().includes(searchLower)
      )
    }
    
    return true
  })
})

// =========================================================================
// 历史记忆系统状态 (History System State)
// =========================================================================

// 会话列表
const historySessions = ref([])
const selectedSession = ref(null)
const sessionDetail = ref(null)

// 统计信息
const historyStats = ref({
  total_sessions: 0,
  total_memory_items: 0,
  memory_types: {}
})

// 加载状态
const isLoadingHistory = ref(false)
const isLoadingDetail = ref(false)

// 展开状态（用于控制会话详情的展开/折叠）
const expandedSessionId = ref(null)

// =========================================================================
// 配置系统状态 (Config System State)
// =========================================================================

// 配置数据
const systemConfig = ref(null)

// 加载状态
const isLoadingConfig = ref(false)
const configLoadError = ref(null)

// =========================================================================
// 2. 核心逻辑方法 (Core Methods)
// =========================================================================

/**
 * 日志系统功能 (Log System Functions)
 */

// 添加日志条目
const addLog = (entry) => {
  if (logPaused.value) return
  
  logs.value.push({
    id: Date.now() + Math.random(),
    timestamp: new Date(),
    source: 'backend',
    ...entry
  })
  
  // 环形缓冲区：超过1000条删除最旧的
  if (logs.value.length > MAX_LOGS) {
    logs.value.shift()
  }
  
  // 自动滚动到最新（如果在底部）
  nextTick(() => {
    if (isLogScrollAtBottom.value && logContainer.value) {
      scrollLogToBottom()
    }
  })
}

// 滚动日志到底部
const scrollLogToBottom = () => {
  if (logContainer.value) {
    logContainer.value.scrollTop = logContainer.value.scrollHeight
  }
}

// 监听日志容器滚动，判断是否在底部
const handleLogScroll = () => {
  if (logContainer.value) {
    const { scrollTop, scrollHeight, clientHeight } = logContainer.value
    isLogScrollAtBottom.value = scrollHeight - scrollTop - clientHeight < 50
  }
}

// 切换级别过滤
const toggleLevelFilter = (level) => {
  const index = logFilters.value.levels.indexOf(level)
  if (index > -1) {
    logFilters.value.levels.splice(index, 1)
  } else {
    logFilters.value.levels.push(level)
  }
}

// 清空日志
const clearLogs = () => {
  if (confirm('确定要清空所有日志吗？')) {
    logs.value = []
  }
}

// 导出日志
const exportLogs = () => {
  const data = filteredLogs.value.map(log => ({
    时间: formatLogTime(log.timestamp, 'full'),
    级别: log.level,
    模块: log.module || '',
    函数: log.function || '',
    行号: log.line || '',
    消息: log.message,
    堆栈: log.trace || ''
  }))
  
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `logs_${new Date().toISOString().replace(/[:.]/g, '-')}.json`
  a.click()
  URL.revokeObjectURL(url)
}

/**
 * 格式化日志时间
 */
const formatLogTime = (timestamp, format = 'short') => {
  const date = new Date(timestamp)
  if (format === 'full') {
    return date.toISOString()
  }
  return date.toLocaleTimeString('zh-CN', { 
    hour: '2-digit', 
    minute: '2-digit', 
    second: '2-digit',
    hour12: false 
  })
}

/**
 * 历史记录功能方法 (History Methods)
 */

/**
 * 加载历史会话列表
 */
const loadHistorySessions = async () => {
  if (isLoadingHistory.value) return
  
  isLoadingHistory.value = true
  
  try {
    const response = await fetch('/api/history/sessions?count=10')
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    const data = await response.json()
    historySessions.value = data
    
    // 同时加载统计信息
    await loadHistoryStatistics()
    
    console.log('[History] Loaded sessions:', data.length)
  } catch (error) {
    console.error('[History] Failed to load sessions:', error)
    alert('加载历史记录失败，请稍后重试')
  } finally {
    isLoadingHistory.value = false
  }
}

/**
 * 加载指定会话的详细内容
 */
const loadSessionDetail = async (sessionId) => {
  if (isLoadingDetail.value) return
  
  isLoadingDetail.value = true
  
  try {
    const response = await fetch(`/api/history/session/${sessionId}`)
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    const data = await response.json()
    sessionDetail.value = data
    selectedSession.value = sessionId
    expandedSessionId.value = sessionId
    
    console.log('[History] Loaded session detail:', sessionId)
  } catch (error) {
    console.error('[History] Failed to load session detail:', error)
    alert('加载对话详情失败，请稍后重试')
  } finally {
    isLoadingDetail.value = false
  }
}

/**
 * 加载统计信息
 */
const loadHistoryStatistics = async () => {
  try {
    const response = await fetch('/api/history/statistics')
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    const data = await response.json()
    historyStats.value = data
    
    console.log('[History] Loaded statistics:', data)
  } catch (error) {
    console.error('[History] Failed to load statistics:', error)
  }
}

/**
 * 刷新历史记录
 */
const refreshHistory = async () => {
  await loadHistorySessions()
}

/**
 * 切换会话详情的展开状态
 */
const toggleSessionDetail = async (sessionId) => {
  if (expandedSessionId.value === sessionId) {
    // 如果当前已展开，则折叠
    expandedSessionId.value = null
    selectedSession.value = null
    sessionDetail.value = null
  } else {
    // 加载并展开
    await loadSessionDetail(sessionId)
  }
}

/**
 * 格式化历史记录时间戳
 */
const formatHistoryTime = (timestamp) => {
  const date = new Date(timestamp)
  const now = new Date()
  const diffMs = now - date
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))
  
  if (diffHours < 1) {
    return '刚刚'
  } else if (diffHours < 24) {
    return `${diffHours} 小时前`
  } else if (diffDays < 7) {
    return `${diffDays} 天前`
  } else {
    return date.toLocaleDateString('zh-CN', { 
      month: 'long', 
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }
}

/**
 * 格式化消息时间戳
 */
const formatMessageTime = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', { 
    hour: '2-digit', 
    minute: '2-digit',
    second: '2-digit'
  })
}

/**
 * 配置系统功能方法 (Config Methods)
 */

/**
 * 加载系统配置
 */
const loadSystemConfig = async () => {
  if (isLoadingConfig.value) return
  
  isLoadingConfig.value = true
  configLoadError.value = null
  
  try {
    const response = await fetch('/api/config/system')
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    const data = await response.json()
    systemConfig.value = data
    
    console.log('[Config] Loaded system config:', data)
  } catch (error) {
    console.error('[Config] Failed to load system config:', error)
    configLoadError.value = error.message || '加载配置失败'
  } finally {
    isLoadingConfig.value = false
  }
}

/**
 * 刷新配置
 */
const refreshConfig = async () => {
  await loadSystemConfig()
}

/**
 * 发送配置到后端
 */
const sendConfig = () => {
    if (!socket.value || socket.value.readyState !== WebSocket.OPEN) return;
    
    const configData = {
        input_mode: isRecording.value ? "audio" : "text",
        output_mode: isVoiceMode.value ? "text_audio" : "text_only"
    };

    console.log("[Config] Sending config update:", configData);
    console.log("[Config] Current Environment:", {
        userAgent: navigator.userAgent,
        audioContextState: audioManager.audioContext ? audioManager.audioContext.state : 'uninitialized',
        isSecureContext: window.isSecureContext,
        protocol: window.location.protocol
    });

    socket.value.send(JSON.stringify({
        type: "config",
        data: configData
    }));
};

/**
 * 切换语音模式
 */
const toggleVoiceMode = () => {
    isVoiceMode.value = !isVoiceMode.value;
    console.log("[UI] User toggled Voice Mode. New state:", isVoiceMode.value ? "ON" : "OFF");
    sendConfig();
};

/**
 * 加载页面基础配置
 */
const fetchPageConfig = async () => {
  try {
    const response = await fetch('/api/config/page_config');
    if (response.ok) {
      const data = await response.json();
      if (data.character_name) characterName.value = data.character_name;
      if (data.first_message) {
        initialMessage.value = data.first_message;
        // 如果当前只有第一条默认消息，则更新它
        if (messages.value.length === 1 && messages.value[0].role === 'ai') {
          messages.value[0].content = data.first_message;
        }
      }
      console.log("[Config] Loaded page config:", data);
    }
  } catch (err) {
    console.error("[Config] Failed to fetch page config:", err);
  }
};

/**
 * 主动热更新：清空当前会话并重新开始，但不包含历史总结
 */
const performHotReload = () => {
    if (!isConnected.value) {
        alert('未连接到服务器，无法执行热更新');
        return;
    }

    // 1. 清空消息列表（保留初始欢迎消息）
    messages.value = [
        {
            id: 1,
            role: 'ai',
            content: initialMessage.value,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            type: 'text'
        }
    ];

    // 2. 重置所有状态
    isTyping.value = false;
    isRecording.value = false;
    isInterrupted.value = false;
    userInput.value = '';
    audioManager.stopPlayback();
    audioManager.stopRecording();

    // 3. 通过WebSocket发送热更新指令给后端
    socket.value.send(JSON.stringify({
        type: "hot_reload"
    }));

    console.log("[UI] Hot reload triggered - context reset without history summary");
};

/**
 * 切换录音状态
 */
const toggleRecording = async () => {
    if (isRecording.value) {
        // 停止录音
        audioManager.stopRecording();
        isRecording.value = false;
        
        // 发送空文本，虽然不需要，但可以作为一种状态结束的标志? 
        // 其实不需要，ASR 服务通常有 VAD，但主动停止更安全
        // 目前后端 ASR 是流式的，停止发送 PCM 数据即可。
    } else {
        // 开始录音
        try {
            await audioManager.startRecording((pcmData) => {
                if (socket.value && socket.value.readyState === WebSocket.OPEN) {
                    socket.value.send(pcmData);
                }
            });
            isRecording.value = true;
            sendConfig();
            
        } catch (e) {
            console.error("Start recording failed:", e);
            alert("无法访问麦克风");
        }
    }
};

/**
 * 停止交互 (打断)
 */
const stopInteraction = () => {
    // 标记为打断状态，开始丢弃后续音频包
    isInterrupted.value = true;

    // 1. 停止前端音频播放
    audioManager.stopPlayback();
    
    // 2. 发送打断信号给后端
    if (socket.value && socket.value.readyState === WebSocket.OPEN) {
        socket.value.send(JSON.stringify({
            type: "interrupt"
        }));
    }
    
    // 3. 更新本地状态
    isTyping.value = false;
    isRecording.value = false; // 如果正在录音也停止
    audioManager.stopRecording(); // 确保录音停止
    console.log("[UI] Interaction stopped by user.");
};

/**
 * 滚动到底部方法
 * 使用 nextTick 确保在 DOM 更新后执行滚动操作
 */
const scrollToBottom = async () => {
  await nextTick()
  if (chatContainer.value) {
    // 设置 scrollTop 为 scrollHeight，即滚动到最底部
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
}

/**
 * WebSocket 连接逻辑
 */
const connectWebSocket = () => {
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  // 如果是开发环境，可能需要指定端口 8000
  const wsHost = import.meta.env.DEV ? 'localhost:8000' : window.location.host;
  const wsUrl = `${wsProtocol}//${wsHost}/ws/chat`;

  socket.value = new WebSocket(wsUrl);

  socket.value.onopen = () => {
    console.log('WebSocket connected');
    isConnected.value = true;
    if (reconnectInterval.value) {
      clearInterval(reconnectInterval.value);
      reconnectInterval.value = null;
    }

    // 发送初始配置
    sendConfig();
  };

  socket.value.onmessage = async (event) => {
    // 处理文本消息 (JSON)
    if (typeof event.data === 'string') {
      try {
        const message = JSON.parse(event.data);
        handleSocketMessage(message);
      } catch (e) {
        console.error('Failed to parse websocket message:', e);
      }
    } else if (event.data instanceof ArrayBuffer || event.data instanceof Blob) {
      // 检查是否处于打断状态，如果是，则丢弃所有音频数据
      if (isInterrupted.value) {
          return;
      }
      
      // 处理二进制消息 (音频)
      try {
          // 如果是 Blob (默认情况), 需要先转 ArrayBuffer
          let arrayBuffer;
          if (event.data instanceof Blob) {
              arrayBuffer = await event.data.arrayBuffer();
          } else {
              arrayBuffer = event.data;
          }
          
          if (arrayBuffer.byteLength > 0) {
              audioManager.playPCM(arrayBuffer);
          }
      } catch (e) {
          console.error('Error processing audio data:', e);
      }
    }
  };

  socket.value.onclose = () => {
    console.log('WebSocket disconnected');
    isConnected.value = false;
    // 尝试重连
    if (!reconnectInterval.value) {
      reconnectInterval.value = setInterval(() => {
        console.log('Attempting to reconnect...');
        connectWebSocket();
      }, 3000);
    }
  };

  socket.value.onerror = (error) => {
    console.error('WebSocket error:', error);
  };
};

/**
 * 处理 WebSocket 消息
 */
const handleSocketMessage = async (message) => {
  if (message.type === 'text_stream') {
    const content = message.content;
    
    // 停止 "正在输入" 状态
    isTyping.value = false;

    // 检查最后一条消息是否是 AI 的
    const lastMessage = messages.value[messages.value.length - 1];
    
    if (lastMessage && lastMessage.role === 'ai' && !lastMessage.isComplete) {
      // 追加内容
      lastMessage.content += content;
    } else {
      // 创建新的 AI 消息
      messages.value.push({
        id: Date.now(),
        role: 'ai',
        content: content,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        type: 'text',
        isComplete: false // 标记消息是否正在接收中
      });
    }
    await scrollToBottom();
  } else if (message.type === 'pong') {
    // 心跳回应
  } else if (message.type === 'state_change') {
      console.log('Backend state changed:', message.state);
      backendState.value = message.state;
      
      // 如果状态变为 idle 或 interrupted，停止 typing 动画
      if (message.state === 'idle' || message.state === 'interrupted') {
          isTyping.value = false;
      }
  } else if (message.type === 'log_entry') {
      // 处理后端日志推送
      if (!logPaused.value) {
        addLog(message.data);
      }
  }
};

/**
 * 发送消息处理函数
 */
const sendMessage = async () => {
  if (!userInput.value.trim()) return;
  if (!isConnected.value) {
    alert('未连接到服务器，请稍后重试');
    return;
  }

  const content = userInput.value;

  // 重置打断标志
  isInterrupted.value = false;

  // 1. 添加用户消息
  messages.value.push({
    id: Date.now(),
    role: 'user',
    content: content,
    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    type: 'text'
  });

  // 标记上一条 AI 消息为已完成（如果有），防止追加到错误的 bubble
  const lastMessage = messages.value[messages.value.length - 2]; // -1 is user, -2 is ai
  if (lastMessage && lastMessage.role === 'ai') {
    lastMessage.isComplete = true;
  }

  // 清空输入框并滚动
  userInput.value = '';
  await scrollToBottom();

  // 2. 开启 AI 正在输入状态
  isTyping.value = true;
  
  // 3. 发送 WebSocket 消息
  // 对应后端 backend/brain.py 中 _dispatch_action 处理的 "user_text"
  socket.value.send(JSON.stringify({
    type: "user_text",
    content: content
  }));
};

/**
 * 切换侧边栏显示状态
 */
const toggleSidebar = () => {
  showSidebar.value = !showSidebar.value
}

/**
 * 切换标签页
 */
const handleTabChange = (tabId) => {
  activeTab.value = tabId
  console.log('[UI] Tab changed to:', tabId)
  
  // 首次进入历史页面时自动加载数据
  if (tabId === 'history' && historySessions.value.length === 0) {
    console.log('[History] First time entering history tab, loading data...')
    loadHistorySessions()
  }
  
  // 首次进入配置页面时自动加载配置
  if (tabId === 'settings' && !systemConfig.value) {
    console.log('[Config] First time entering settings tab, loading config...')
    loadSystemConfig()
  }
}

// 生命周期钩子
onMounted(() => {
  fetchPageConfig();
  connectWebSocket();
});

onUnmounted(() => {
  if (socket.value) {
    socket.value.close();
  }
  if (reconnectInterval.value) {
    clearInterval(reconnectInterval.value);
  }
});
</script>

<template>
  <!-- 
    主布局容器 
    - max-w-[1600px]: 限制最大宽度，避免在大屏上过于拉伸
    - h-[90vh]: 桌面端高度为视口的 90%
    - md:rounded-2xl: 桌面端显示圆角
  -->
  <div class="flex w-full h-full md:h-[90vh] max-w-[1600px] bg-white md:rounded-2xl shadow-xl overflow-hidden border border-gray-200">
    
    <!-- 
      侧边栏 (Sidebar)
      - 使用动态 class 控制显示/隐藏
      - hidden md:flex: 默认在移动端隐藏，桌面端显示 (除非 showSidebar 改变)
    -->
    <Sidebar 
      :class="{'hidden md:flex': !showSidebar, 'flex': showSidebar}" 
      class="w-full md:w-80 shrink-0"
      :active-tab="activeTab"
      @tab-change="handleTabChange"
    />

    <!-- 右侧主内容区域 -->
    <div class="flex-1 flex flex-col h-full relative bg-gray-50">
      
      <!-- 聊天界面 -->
      <div v-show="activeTab === 'chat'" class="flex-1 flex flex-col h-full">
        <!-- 
          顶部标题栏 (Header)
          - z-10: 确保阴影覆盖在内容之上
        -->
        <div class="h-16 px-6 bg-white border-b border-gray-100 flex items-center justify-between z-10">
          <div class="flex items-center gap-4">
            <!-- 移动端侧边栏切换按钮 -->
            <button @click="toggleSidebar" class="p-2 text-gray-500 hover:bg-gray-100 rounded-lg md:hidden">
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
            <!-- 语音模式开关 -->
            <button 
              @click="toggleVoiceMode" 
              class="px-3 py-1.5 rounded-full text-xs font-medium transition-colors border flex items-center gap-2"
              :class="isVoiceMode ? 'bg-blue-50 text-blue-600 border-blue-200' : 'bg-gray-50 text-gray-500 border-gray-200'"
              title="Toggle Voice Output"
            >
              <i class="fas" :class="isVoiceMode ? 'fa-volume-up' : 'fa-volume-mute'"></i>
              <span class="hidden md:inline">{{ isVoiceMode ? 'Voice On' : 'Voice Off' }}</span>
            </button>

            <!-- 主动热更新按钮 -->
            <button 
              @click="performHotReload"
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

            <button class="w-9 h-9 flex items-center justify-center rounded-full text-gray-500 hover:bg-gray-100 transition-colors">
              <i class="fas fa-search"></i>
            </button>
            <button class="w-9 h-9 flex items-center justify-center rounded-full text-gray-500 hover:bg-gray-100 transition-colors">
              <i class="fas fa-ellipsis-v"></i>
            </button>
          </div>
        </div>

        <!-- 
          消息流区域 (Messages Area)
          - flex-1: 占据剩余高度
          - overflow-y-auto: 内容过多时滚动
        -->
        <div ref="chatContainer" class="flex-1 overflow-y-auto p-4 md:p-6 space-y-6 scroll-smooth">
          <!-- 循环渲染消息气泡 -->
          <MessageBubble 
            v-for="msg in messages" 
            :key="msg.id" 
            :message="msg" 
          />
          
          <!-- 正在输入提示 (Typing Indicator) -->
          <div v-if="isTyping" class="flex justify-start animate-fade-in">
            <div class="bg-white border border-gray-100 rounded-2xl rounded-tl-none py-3 px-4 shadow-sm flex items-center gap-1">
              <!-- 三个跳动的圆点动画 -->
              <div class="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0s"></div>
              <div class="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0.2s"></div>
              <div class="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0.4s"></div>
            </div>
          </div>
        </div>

        <!-- 
          底部输入区域 (Input Area)
          - border-t: 顶部边框
        -->
        <div class="p-4 md:p-6 bg-white border-t border-gray-100">
          <div class="max-w-4xl mx-auto">
            <!-- 快捷操作栏 (可选，目前注释掉) -->
            <!-- <div class="flex gap-2 mb-3 overflow-x-auto pb-2 scrollbar-hide">...</div> -->

            <!-- 输入框容器 -->
            <div class="relative bg-gray-50 border border-gray-200 rounded-2xl p-2 focus-within:ring-2 focus-within:ring-blue-100 focus-within:border-blue-400 transition-all shadow-sm">
              <!-- 文本域: 支持多行输入 -->
              <textarea 
                v-model="userInput"
                @keydown.enter.prevent="sendMessage"
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
                    @click="toggleRecording"
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
                    @click="stopInteraction"
                    class="w-10 h-10 rounded-full flex items-center justify-center transition-all duration-200 shadow-md bg-red-50 text-red-500 hover:bg-red-500 hover:text-white border border-red-200 animate-pulse"
                    title="Stop / Interrupt"
                  >
                    <i class="fas fa-stop text-sm"></i>
                  </button>

                  <!-- 发送按钮 -->
                  <button 
                    @click="sendMessage"
                    :disabled="!userInput.trim() || !isConnected"
                    :class="{'opacity-50 cursor-not-allowed': !userInput.trim() || !isConnected, 'hover:bg-blue-600 hover:shadow-lg': userInput.trim() && isConnected}"
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
      </div>

      <!-- 历史界面 -->
      <div v-show="activeTab === 'history'" class="flex-1 flex flex-col h-full bg-gray-50">
        <!-- 顶部工具栏 -->
        <div class="h-16 px-6 bg-white border-b border-gray-200 flex items-center justify-between shrink-0">
          <div class="flex items-center gap-4">
            <h2 class="font-bold text-gray-900 text-lg">历史记录</h2>
            <div class="flex items-center gap-2 text-sm">
              <span class="px-2 py-1 rounded-full bg-blue-50 text-blue-600 text-xs font-medium">
                <i class="fas fa-comments mr-1"></i>{{ historyStats.total_sessions }} 次对话
              </span>
              <span class="px-2 py-1 rounded-full bg-green-50 text-green-600 text-xs font-medium">
                <i class="fas fa-brain mr-1"></i>{{ historyStats.total_memory_items }} 条记忆
              </span>
            </div>
          </div>
          
          <div class="flex items-center gap-3">
            <!-- 刷新按钮 -->
            <button 
              @click="refreshHistory"
              :disabled="isLoadingHistory"
              class="px-3 py-1.5 bg-blue-500 text-white rounded-lg text-sm hover:bg-blue-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              <i class="fas fa-sync" :class="{ 'animate-spin': isLoadingHistory }"></i>
              {{ isLoadingHistory ? '加载中...' : '刷新' }}
            </button>
          </div>
        </div>
        
        <!-- 主内容区域 -->
        <div class="flex-1 overflow-y-auto p-6">
          <!-- 加载状态 -->
          <div v-if="isLoadingHistory && historySessions.length === 0" class="flex flex-col items-center justify-center h-full text-gray-400 py-20">
            <i class="fas fa-spinner fa-spin text-5xl mb-4"></i>
            <p class="text-lg font-medium">加载历史记录中...</p>
          </div>
          
          <!-- 空状态 -->
          <div v-else-if="historySessions.length === 0" class="flex flex-col items-center justify-center h-full text-gray-400 py-20">
            <i class="fas fa-history text-5xl mb-4"></i>
            <p class="text-lg font-medium">暂无历史记录</p>
            <p class="text-sm mt-2">开始对话后，历史记录将显示在这里</p>
          </div>
          
          <!-- 会话列表 -->
          <div v-else class="max-w-4xl mx-auto space-y-4">
            <div 
              v-for="session in historySessions" 
              :key="session.session_id"
              class="bg-white rounded-lg border border-gray-200 shadow-sm hover:shadow-md transition-shadow"
            >
              <!-- 会话头部 -->
              <div 
                @click="toggleSessionDetail(session.session_id)"
                class="p-4 cursor-pointer hover:bg-gray-50 transition-colors"
              >
                <div class="flex items-start justify-between">
                  <div class="flex-1">
                    <div class="flex items-center gap-2 mb-2">
                      <i class="fas fa-comment-dots text-blue-500"></i>
                      <span class="text-xs text-gray-500">{{ formatHistoryTime(session.created_at) }}</span>
                      <span class="text-xs text-gray-400">{{ session.message_count }} 条消息</span>
                    </div>
                    <p class="text-gray-700 text-sm leading-relaxed">{{ session.summary }}</p>
                    
                    <!-- 关键要点标签 -->
                    <div v-if="session.key_points && session.key_points.length > 0" class="flex flex-wrap gap-2 mt-3">
                      <span 
                        v-for="(point, idx) in session.key_points.slice(0, 3)" 
                        :key="idx"
                        class="px-2 py-1 bg-blue-50 text-blue-600 text-xs rounded-full"
                      >
                        {{ point }}
                      </span>
                      <span 
                        v-if="session.key_points.length > 3"
                        class="px-2 py-1 bg-gray-100 text-gray-500 text-xs rounded-full"
                      >
                        +{{ session.key_points.length - 3 }}
                      </span>
                    </div>
                  </div>
                  
                  <!-- 展开/折叠图标 -->
                  <div class="ml-4">
                    <i 
                      class="fas transition-transform text-gray-400"
                      :class="expandedSessionId === session.session_id ? 'fa-chevron-up' : 'fa-chevron-down'"
                    ></i>
                  </div>
                </div>
              </div>
              
              <!-- 会话详情（展开时显示） -->
              <div 
                v-if="expandedSessionId === session.session_id"
                class="border-t border-gray-200 bg-gray-50"
              >
                <!-- 加载中状态 -->
                <div v-if="isLoadingDetail" class="p-8 flex items-center justify-center">
                  <i class="fas fa-spinner fa-spin text-blue-500 mr-2"></i>
                  <span class="text-gray-600">加载对话详情...</span>
                </div>
                
                <!-- 对话详情 -->
                <div v-else-if="sessionDetail && sessionDetail.session_id === session.session_id" class="p-4 space-y-3 max-h-96 overflow-y-auto">
                  <div 
                    v-for="(msg, idx) in sessionDetail.messages" 
                    :key="idx"
                    class="flex"
                    :class="msg.role === 'user' ? 'justify-end' : 'justify-start'"
                  >
                    <div 
                      class="max-w-[80%] rounded-lg px-4 py-2 text-sm"
                      :class="msg.role === 'user' 
                        ? 'bg-blue-500 text-white rounded-br-none' 
                        : 'bg-white border border-gray-200 rounded-bl-none'"
                    >
                      <div class="flex items-center gap-2 mb-1 text-xs opacity-70">
                        <i class="fas" :class="msg.role === 'user' ? 'fa-user' : 'fa-robot'"></i>
                        <span>{{ msg.role === 'user' ? '用户' : 'AI' }}</span>
                        <span v-if="msg.timestamp">{{ formatMessageTime(msg.timestamp) }}</span>
                      </div>
                      <p class="whitespace-pre-wrap">{{ msg.content }}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 配置界面 -->
      <div v-show="activeTab === 'settings'" class="flex-1 flex flex-col h-full bg-gray-50">
        <!-- 顶部工具栏 -->
        <div class="h-16 px-6 bg-white border-b border-gray-200 flex items-center justify-between shrink-0">
          <div class="flex items-center gap-4">
            <h2 class="font-bold text-gray-900 text-lg">系统配置</h2>
            <div class="flex items-center gap-2">
              <span v-if="isConnected" class="flex items-center gap-2 px-2 py-1 rounded-full bg-green-50 text-green-600 text-xs font-medium">
                <span class="w-2 h-2 rounded-full bg-green-500"></span>
                WebSocket 已连接
              </span>
              <span v-else class="flex items-center gap-2 px-2 py-1 rounded-full bg-red-50 text-red-600 text-xs font-medium">
                <span class="w-2 h-2 rounded-full bg-red-500"></span>
                WebSocket 未连接
              </span>
            </div>
          </div>
          
          <div class="flex items-center gap-3">
            <!-- 刷新按钮 -->
            <button 
              @click="refreshConfig"
              :disabled="isLoadingConfig"
              class="px-3 py-1.5 bg-blue-500 text-white rounded-lg text-sm hover:bg-blue-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              <i class="fas fa-sync" :class="{ 'animate-spin': isLoadingConfig }"></i>
              {{ isLoadingConfig ? '加载中...' : '刷新' }}
            </button>
          </div>
        </div>
        
        <!-- 主内容区域 -->
        <div class="flex-1 overflow-y-auto p-6">
          <!-- 加载状态 -->
          <div v-if="isLoadingConfig && !systemConfig" class="flex flex-col items-center justify-center h-full text-gray-400 py-20">
            <i class="fas fa-spinner fa-spin text-5xl mb-4"></i>
            <p class="text-lg font-medium">加载配置中...</p>
          </div>
          
          <!-- 错误状态 -->
          <div v-else-if="configLoadError" class="flex flex-col items-center justify-center h-full text-gray-400 py-20">
            <i class="fas fa-exclamation-triangle text-5xl mb-4 text-red-400"></i>
            <p class="text-lg font-medium text-red-600">加载配置失败</p>
            <p class="text-sm mt-2 text-gray-600">{{ configLoadError }}</p>
            <button 
              @click="refreshConfig"
              class="mt-4 px-4 py-2 bg-blue-500 text-white rounded-lg text-sm hover:bg-blue-600 transition-colors flex items-center gap-2"
            >
              <i class="fas fa-redo"></i>
              重试
            </button>
          </div>
          
          <!-- 配置内容 -->
          <div v-else-if="systemConfig" class="max-w-5xl mx-auto space-y-6">
            <!-- 输入输出配置 -->
            <div class="bg-white rounded-lg border border-gray-200 shadow-sm">
              <div class="px-6 py-4 border-b border-gray-200">
                <h3 class="font-semibold text-gray-900 flex items-center gap-2">
                  <i class="fas fa-exchange-alt text-blue-500"></i>
                  输入输出模式
                </h3>
              </div>
              <div class="p-6 space-y-4">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div class="flex justify-between items-center p-4 bg-gray-50 rounded-lg">
                    <div>
                      <div class="text-sm font-medium text-gray-700">输入模式</div>
                      <div class="text-xs text-gray-500 mt-1">当前支持的输入方式</div>
                    </div>
                    <div class="px-3 py-1.5 bg-blue-100 text-blue-700 rounded-full text-sm font-medium">
                      {{ systemConfig.input_output.input_mode === 'text' ? '文本' : '语音' }}
                    </div>
                  </div>
                  <div class="flex justify-between items-center p-4 bg-gray-50 rounded-lg">
                    <div>
                      <div class="text-sm font-medium text-gray-700">输出模式</div>
                      <div class="text-xs text-gray-500 mt-1">当前的回复方式</div>
                    </div>
                    <div class="px-3 py-1.5 bg-green-100 text-green-700 rounded-full text-sm font-medium">
                      {{ systemConfig.input_output.output_mode === 'text_only' ? '纯文本' : '文本+语音' }}
                    </div>
                  </div>
                </div>
                <div class="p-4 bg-blue-50 rounded-lg">
                  <div class="text-xs text-blue-800 font-medium mb-2">可用模式</div>
                  <div class="flex flex-wrap gap-2">
                    <span v-for="mode in systemConfig.input_output.available_input_modes" :key="mode" 
                          class="px-2 py-1 bg-white text-blue-600 text-xs rounded border border-blue-200">
                      输入: {{ mode === 'text' ? '文本' : '语音' }}
                    </span>
                    <span v-for="mode in systemConfig.input_output.available_output_modes" :key="mode" 
                          class="px-2 py-1 bg-white text-green-600 text-xs rounded border border-green-200">
                      输出: {{ mode === 'text_only' ? '纯文本' : '文本+语音' }}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <!-- AI助手配置 -->
            <div class="bg-white rounded-lg border border-gray-200 shadow-sm">
              <div class="px-6 py-4 border-b border-gray-200">
                <h3 class="font-semibold text-gray-900 flex items-center gap-2">
                  <i class="fas fa-robot text-purple-500"></i>
                  AI助手信息
                </h3>
              </div>
              <div class="p-6 space-y-4">
                <div class="flex items-start gap-4">
                  <div class="w-16 h-16 rounded-full bg-gradient-to-br from-purple-400 to-blue-500 flex items-center justify-center text-white text-2xl shrink-0">
                    <i class="fas fa-robot"></i>
                  </div>
                  <div class="flex-1">
                    <div class="text-lg font-semibold text-gray-900">{{ systemConfig.ai_assistant.display_name }}</div>
                    <div class="text-sm text-gray-500 mt-1">Character ID: {{ systemConfig.ai_assistant.character_name }}</div>
                    <div class="text-sm text-gray-700 mt-3 leading-relaxed max-h-32 overflow-y-auto">
                      {{ systemConfig.ai_assistant.description || '暂无描述' }}
                    </div>
                  </div>
                </div>
                <div class="p-4 bg-purple-50 rounded-lg">
                  <div class="text-xs font-medium text-purple-800 mb-2">性格特征</div>
                  <div class="text-sm text-purple-700 leading-relaxed max-h-24 overflow-y-auto">
                    {{ systemConfig.ai_assistant.personality || '暂无性格设定' }}
                  </div>
                </div>
                <div class="p-4 bg-blue-50 rounded-lg">
                  <div class="text-xs font-medium text-blue-800 mb-2">首条欢迎语</div>
                  <div class="text-sm text-blue-700">
                    {{ systemConfig.ai_assistant.first_message || '暂无欢迎语' }}
                  </div>
                </div>
              </div>
            </div>

            <!-- 大语言模型配置 -->
            <div class="bg-white rounded-lg border border-gray-200 shadow-sm">
              <div class="px-6 py-4 border-b border-gray-200">
                <h3 class="font-semibold text-gray-900 flex items-center gap-2">
                  <i class="fas fa-brain text-pink-500"></i>
                  大语言模型 (LLM)
                </h3>
              </div>
              <div class="p-6">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div class="p-4 bg-gray-50 rounded-lg">
                    <div class="text-xs text-gray-500 mb-1">对话模型</div>
                    <div class="text-sm font-medium text-gray-900">{{ systemConfig.llm.chat_model }}</div>
                  </div>
                  <div class="p-4 bg-gray-50 rounded-lg">
                    <div class="text-xs text-gray-500 mb-1">服务提供商</div>
                    <div class="text-sm font-medium text-gray-900">{{ systemConfig.llm.chat_provider }}</div>
                  </div>
                  <div class="p-4 bg-gray-50 rounded-lg">
                    <div class="text-xs text-gray-500 mb-1">温度 (Temperature)</div>
                    <div class="text-sm font-medium text-gray-900">{{ systemConfig.llm.temperature }}</div>
                  </div>
                  <div class="p-4 bg-gray-50 rounded-lg">
                    <div class="text-xs text-gray-500 mb-1">最大Token数</div>
                    <div class="text-sm font-medium text-gray-900">{{ systemConfig.llm.max_tokens || '未限制' }}</div>
                  </div>
                  <div class="p-4 bg-gray-50 rounded-lg md:col-span-2">
                    <div class="text-xs text-gray-500 mb-1">嵌入模型</div>
                    <div class="text-sm font-medium text-gray-900">{{ systemConfig.llm.embedding_model }}</div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 语音服务配置 -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
              <!-- TTS配置 -->
              <div class="bg-white rounded-lg border border-gray-200 shadow-sm">
                <div class="px-6 py-4 border-b border-gray-200">
                  <h3 class="font-semibold text-gray-900 flex items-center gap-2">
                    <i class="fas fa-volume-up text-green-500"></i>
                    文本转语音 (TTS)
                  </h3>
                </div>
                <div class="p-6 space-y-3">
                  <div class="flex justify-between items-center">
                    <span class="text-sm text-gray-600">启用状态</span>
                    <span class="px-2 py-1 rounded-full text-xs font-medium"
                          :class="systemConfig.tts.enabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'">
                      {{ systemConfig.tts.enabled ? '已启用' : '未启用' }}
                    </span>
                  </div>
                  <div class="flex justify-between items-center">
                    <span class="text-sm text-gray-600">引擎</span>
                    <span class="text-sm font-medium text-gray-900">{{ systemConfig.tts.engine }}</span>
                  </div>
                  <div class="flex justify-between items-center">
                    <span class="text-sm text-gray-600">角色</span>
                    <span class="text-sm font-medium text-gray-900">{{ systemConfig.tts.active_character }}</span>
                  </div>
                  <div class="flex justify-between items-center">
                    <span class="text-sm text-gray-600">语言</span>
                    <span class="text-sm font-medium text-gray-900">{{ systemConfig.tts.language }}</span>
                  </div>
                  <div class="pt-3 border-t border-gray-200">
                    <div class="text-xs text-gray-500 mb-2">服务器配置</div>
                    <div class="text-sm text-gray-700">
                      {{ systemConfig.tts.server_host }}:{{ systemConfig.tts.server_port }}
                    </div>
                  </div>
                </div>
              </div>

              <!-- ASR配置 -->
              <div class="bg-white rounded-lg border border-gray-200 shadow-sm">
                <div class="px-6 py-4 border-b border-gray-200">
                  <h3 class="font-semibold text-gray-900 flex items-center gap-2">
                    <i class="fas fa-microphone text-red-500"></i>
                    语音识别 (ASR)
                  </h3>
                </div>
                <div class="p-6 space-y-3">
                  <div class="flex justify-between items-center">
                    <span class="text-sm text-gray-600">启用状态</span>
                    <span class="px-2 py-1 rounded-full text-xs font-medium"
                          :class="systemConfig.asr.enabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'">
                      {{ systemConfig.asr.enabled ? '已启用' : '未启用' }}
                    </span>
                  </div>
                  <div class="flex justify-between items-center">
                    <span class="text-sm text-gray-600">引擎</span>
                    <span class="text-sm font-medium text-gray-900">{{ systemConfig.asr.engine }}</span>
                  </div>
                  <div class="flex justify-between items-center">
                    <span class="text-sm text-gray-600">模型</span>
                    <span class="text-sm font-medium text-gray-900">{{ systemConfig.asr.model }}</span>
                  </div>
                  <div class="flex justify-between items-center">
                    <span class="text-sm text-gray-600">语言</span>
                    <span class="text-sm font-medium text-gray-900">{{ systemConfig.asr.language }}</span>
                  </div>
                  <div class="pt-3 border-t border-gray-200">
                    <div class="text-xs text-gray-500 mb-2">音频配置</div>
                    <div class="text-sm text-gray-700">
                      {{ systemConfig.asr.sample_rate }} Hz, {{ systemConfig.asr.channels }} 声道
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 记忆系统配置 -->
            <div class="bg-white rounded-lg border border-gray-200 shadow-sm">
              <div class="px-6 py-4 border-b border-gray-200">
                <h3 class="font-semibold text-gray-900 flex items-center gap-2">
                  <i class="fas fa-database text-indigo-500"></i>
                  记忆系统
                </h3>
              </div>
              <div class="p-6">
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div class="p-4 bg-gray-50 rounded-lg">
                    <div class="text-xs text-gray-500 mb-1">短期记忆长度</div>
                    <div class="text-sm font-medium text-gray-900">{{ systemConfig.memory.max_history_length }} 轮对话</div>
                  </div>
                  <div class="p-4 bg-gray-50 rounded-lg">
                    <div class="text-xs text-gray-500 mb-1">检索数量</div>
                    <div class="text-sm font-medium text-gray-900">Top {{ systemConfig.memory.retrieval_top_k }}</div>
                  </div>
                  <div class="p-4 bg-gray-50 rounded-lg">
                    <div class="text-xs text-gray-500 mb-1">相似度阈值</div>
                    <div class="text-sm font-medium text-gray-900">{{ systemConfig.memory.retrieval_threshold }}</div>
                  </div>
                  <div class="p-4 bg-gray-50 rounded-lg md:col-span-3">
                    <div class="text-xs text-gray-500 mb-1">嵌入模型</div>
                    <div class="text-sm font-medium text-gray-900">{{ systemConfig.memory.embedding_model }}</div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 用户档案配置 -->
            <div class="bg-white rounded-lg border border-gray-200 shadow-sm">
              <div class="px-6 py-4 border-b border-gray-200">
                <h3 class="font-semibold text-gray-900 flex items-center gap-2">
                  <i class="fas fa-user text-yellow-500"></i>
                  用户档案
                </h3>
              </div>
              <div class="p-6">
                <div v-if="systemConfig.user_profile.name || systemConfig.user_profile.nickname" class="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div v-if="systemConfig.user_profile.name" class="p-4 bg-gray-50 rounded-lg">
                    <div class="text-xs text-gray-500 mb-1">姓名</div>
                    <div class="text-sm font-medium text-gray-900">{{ systemConfig.user_profile.name }}</div>
                  </div>
                  <div v-if="systemConfig.user_profile.nickname" class="p-4 bg-gray-50 rounded-lg">
                    <div class="text-xs text-gray-500 mb-1">昵称</div>
                    <div class="text-sm font-medium text-gray-900">{{ systemConfig.user_profile.nickname }}</div>
                  </div>
                  <div v-if="systemConfig.user_profile.age" class="p-4 bg-gray-50 rounded-lg">
                    <div class="text-xs text-gray-500 mb-1">年龄</div>
                    <div class="text-sm font-medium text-gray-900">{{ systemConfig.user_profile.age }} 岁</div>
                  </div>
                  <div v-if="systemConfig.user_profile.gender" class="p-4 bg-gray-50 rounded-lg">
                    <div class="text-xs text-gray-500 mb-1">性别</div>
                    <div class="text-sm font-medium text-gray-900">{{ systemConfig.user_profile.gender }}</div>
                  </div>
                  <div v-if="systemConfig.user_profile.relationship_with_ai" class="p-4 bg-gray-50 rounded-lg md:col-span-2">
                    <div class="text-xs text-gray-500 mb-1">与AI的关系</div>
                    <div class="text-sm font-medium text-gray-900">{{ systemConfig.user_profile.relationship_with_ai }}</div>
                  </div>
                </div>
                <div v-else class="text-center py-8 text-gray-400">
                  <i class="fas fa-user-slash text-3xl mb-2"></i>
                  <p class="text-sm">未配置用户信息</p>
                </div>
              </div>
            </div>

            <!-- 系统配置 -->
            <div class="bg-white rounded-lg border border-gray-200 shadow-sm">
              <div class="px-6 py-4 border-b border-gray-200">
                <h3 class="font-semibold text-gray-900 flex items-center gap-2">
                  <i class="fas fa-cog text-gray-500"></i>
                  系统设置
                </h3>
              </div>
              <div class="p-6">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div class="p-4 bg-gray-50 rounded-lg">
                    <div class="text-xs text-gray-500 mb-1">应用名称</div>
                    <div class="text-sm font-medium text-gray-900">{{ systemConfig.system.app_name }}</div>
                  </div>
                  <div class="p-4 bg-gray-50 rounded-lg">
                    <div class="text-xs text-gray-500 mb-1">日志级别</div>
                    <div class="text-sm font-medium text-gray-900">{{ systemConfig.system.log_level }}</div>
                  </div>
                  <div class="p-4 bg-gray-50 rounded-lg">
                    <div class="text-xs text-gray-500 mb-1">调试模式</div>
                    <span class="px-2 py-1 rounded-full text-xs font-medium"
                          :class="systemConfig.system.debug ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-600'">
                      {{ systemConfig.system.debug ? '已启用' : '未启用' }}
                    </span>
                  </div>
                  <div v-if="systemConfig.system.data_dir" class="p-4 bg-gray-50 rounded-lg">
                    <div class="text-xs text-gray-500 mb-1">数据目录</div>
                    <div class="text-sm font-medium text-gray-900 truncate" :title="systemConfig.system.data_dir">
                      {{ systemConfig.system.data_dir }}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 日志界面 -->
      <div v-show="activeTab === 'logs'" class="flex-1 flex flex-col h-full bg-gray-50">
        <!-- 顶部工具栏 -->
        <div class="h-16 px-6 bg-white border-b border-gray-200 flex items-center justify-between shrink-0">
          <div class="flex items-center gap-4">
            <h2 class="font-bold text-gray-900 text-lg">系统日志</h2>
            <div class="flex items-center gap-2 text-sm">
              <span class="px-2 py-1 rounded-full bg-red-50 text-red-600 text-xs font-medium">
                <i class="fas fa-times-circle mr-1"></i>{{ logStats.error }}
              </span>
              <span class="px-2 py-1 rounded-full bg-yellow-50 text-yellow-600 text-xs font-medium">
                <i class="fas fa-exclamation-triangle mr-1"></i>{{ logStats.warning }}
              </span>
              <span class="px-2 py-1 rounded-full bg-blue-50 text-blue-600 text-xs font-medium">
                <i class="fas fa-info-circle mr-1"></i>{{ logStats.info }}
              </span>
            </div>
          </div>
          
          <div class="flex items-center gap-3">
            <!-- 搜索框 -->
            <div class="relative">
              <i class="fas fa-search absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-xs"></i>
              <input 
                v-model="logFilters.search"
                type="text"
                placeholder="搜索日志..."
                class="pl-9 pr-4 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 w-48"
              />
            </div>
            
            <!-- 级别过滤下拉菜单 -->
            <div class="relative">
              <button 
                @click="showLevelFilter = !showLevelFilter"
                class="px-3 py-1.5 border border-gray-300 rounded-lg text-sm hover:bg-gray-50 flex items-center gap-2"
              >
                <i class="fas fa-filter"></i>
                <span>级别</span>
                <i class="fas fa-chevron-down text-xs"></i>
              </button>
              
              <!-- 下拉面板 -->
              <div v-if="showLevelFilter" class="absolute top-full right-0 mt-2 bg-white border border-gray-200 rounded-lg shadow-lg p-2 z-10 min-w-[160px]">
                <div v-for="(config, level) in LOG_LEVELS" :key="level" class="flex items-center gap-2 p-2 hover:bg-gray-50 rounded cursor-pointer">
                  <input 
                    type="checkbox" 
                    :checked="logFilters.levels.includes(level)"
                    @change="toggleLevelFilter(level)"
                    class="rounded text-blue-500"
                  />
                  <i class="fas text-sm" :class="[config.icon, config.color]"></i>
                  <span class="text-sm">{{ config.label }}</span>
                </div>
              </div>
            </div>
            
            <!-- 清空日志 -->
            <button 
              @click="clearLogs"
              class="px-3 py-1.5 border border-gray-300 rounded-lg text-sm hover:bg-red-50 hover:border-red-300 hover:text-red-600 transition-colors"
            >
              <i class="fas fa-trash mr-1"></i>清空
            </button>
            
            <!-- 导出日志 -->
            <button 
              @click="exportLogs"
              class="px-3 py-1.5 bg-blue-500 text-white rounded-lg text-sm hover:bg-blue-600 transition-colors"
            >
              <i class="fas fa-download mr-1"></i>导出
            </button>
            
            <!-- 暂停/继续 -->
            <button 
              @click="logPaused = !logPaused"
              class="w-9 h-9 rounded-full flex items-center justify-center border border-gray-300 hover:bg-gray-50 transition-colors"
              :class="logPaused ? 'bg-yellow-50 border-yellow-300 text-yellow-600' : 'text-gray-600'"
              :title="logPaused ? '继续日志' : '暂停日志'"
            >
              <i class="fas text-sm" :class="logPaused ? 'fa-play' : 'fa-pause'"></i>
            </button>
          </div>
        </div>
        
        <!-- 日志列表主体 -->
        <div 
          ref="logContainer" 
          @scroll="handleLogScroll"
          class="flex-1 overflow-y-auto p-4 space-y-2 font-mono text-xs"
        >
          <div 
            v-for="log in filteredLogs" 
            :key="log.id"
            class="flex items-start gap-3 p-3 bg-white border border-gray-200 rounded-lg hover:shadow-sm transition-shadow"
            :class="LOG_LEVELS[log.level]?.bg"
          >
            <!-- 左侧时间 & 级别 -->
            <div class="shrink-0 w-24">
              <div class="text-gray-500 text-[10px] mb-1">{{ formatLogTime(log.timestamp) }}</div>
              <div class="flex items-center gap-1" :class="LOG_LEVELS[log.level]?.color">
                <i class="fas text-xs" :class="LOG_LEVELS[log.level]?.icon"></i>
                <span class="font-bold text-[10px]">{{ log.level }}</span>
              </div>
            </div>
            
            <!-- 中间内容 -->
            <div class="flex-1 min-w-0">
              <div class="text-gray-600 mb-1 text-[11px]">
                <span class="font-semibold">{{ log.module || 'system' }}</span>
                <span v-if="log.function" class="text-gray-400"> :: {{ log.function }}:{{ log.line }}</span>
              </div>
              <div class="text-gray-900 break-words text-xs leading-relaxed">{{ log.message }}</div>
              
              <!-- 堆栈追踪 -->
              <div v-if="log.trace" class="mt-2 p-2 bg-gray-100 rounded text-[9px] overflow-x-auto max-h-32 overflow-y-auto">
                <pre class="whitespace-pre-wrap text-gray-700">{{ log.trace }}</pre>
              </div>
            </div>
          </div>
          
          <!-- 空状态 -->
          <div v-if="filteredLogs.length === 0" class="flex flex-col items-center justify-center h-full text-gray-400 py-20">
            <i class="fas fa-inbox text-5xl mb-4"></i>
            <p class="text-lg font-medium">暂无日志</p>
            <p class="text-sm mt-2">{{ logs.length > 0 ? '当前过滤条件没有匹配的日志' : '等待系统生成日志...' }}</p>
          </div>
        </div>
        
        <!-- 底部状态栏 -->
        <div class="h-10 px-6 bg-white border-t border-gray-200 flex items-center justify-between text-xs text-gray-500 shrink-0">
          <div class="flex items-center gap-4">
            <span>显示 {{ filteredLogs.length }} / {{ logs.length }} 条日志</span>
            <span v-if="logPaused" class="text-yellow-600 font-medium">
              <i class="fas fa-pause-circle mr-1"></i>已暂停
            </span>
          </div>
          <div class="text-gray-400">
            <i class="fas fa-info-circle mr-1"></i>环形缓冲区最多保留 {{ MAX_LOGS }} 条
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 隐藏滚动条但保留滚动功能的工具类 */
.scrollbar-hide::-webkit-scrollbar {
    display: none;
}
.scrollbar-hide {
    -ms-overflow-style: none;
    scrollbar-width: none;
}
</style>
