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

import { ref, nextTick, onMounted, onUnmounted, watch } from 'vue'
import MessageBubble from './MessageBubble.vue'
import Sidebar from './Sidebar.vue'
import { AudioManager } from '../utils/audio.js'

// =========================================================================
// 1. 状态定义 (State Definitions)
// =========================================================================

const audioManager = new AudioManager()

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
    content: '你好！我是你的私人AI助手。有什么我可以帮你的吗？',
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

// 侧边栏显示状态 (桌面端默认显示，移动端默认隐藏)
const showSidebar = ref(true)

// 当前激活的标签页
const activeTab = ref('chat')

// WebSocket 连接实例
const socket = ref(null)
const isConnected = ref(false)
const reconnectInterval = ref(null)

// 角色名称
const characterName = ref('灵依')

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
// 2. 核心逻辑方法 (Core Methods)
// =========================================================================

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
            content: '你好！我是你的私人AI助手。有什么我可以帮你的吗？',
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
            
            // 确保后端知道我们开始语音输入了 (更新 input_mode)
            // 虽然不更新也能工作（后端会自动识别二进制帧），但更新状态更规范
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
}

// 生命周期钩子
onMounted(() => {
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
      <div v-show="activeTab === 'history'" class="flex-1 flex items-center justify-center bg-white">
        <div class="text-center text-gray-400">
          <i class="fas fa-history text-6xl mb-4"></i>
          <p class="text-xl font-medium">历史记录</p>
          <p class="text-sm mt-2">此功能尚未实现</p>
        </div>
      </div>

      <!-- 配置界面 -->
      <div v-show="activeTab === 'settings'" class="flex-1 flex items-center justify-center bg-white">
        <div class="text-center text-gray-400">
          <i class="fas fa-cog text-6xl mb-4"></i>
          <p class="text-xl font-medium">系统配置</p>
          <p class="text-sm mt-2">此功能尚未实现</p>
        </div>
      </div>

      <!-- 日志界面 -->
      <div v-show="activeTab === 'logs'" class="flex-1 flex items-center justify-center bg-white">
        <div class="text-center text-gray-400">
          <i class="fas fa-file-alt text-6xl mb-4"></i>
          <p class="text-xl font-medium">系统日志</p>
          <p class="text-sm mt-2">此功能尚未实现</p>
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
