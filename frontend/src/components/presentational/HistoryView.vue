<script setup>
/**
 * 历史记录视图组件 (Presentational Component)
 * =========================================================================
 * 
 * 【组件类型】Dumb Component（纯展示组件）
 * 【职责】
 * - 显示历史会话列表
 * - 显示会话统计信息
 * - 显示会话详情（消息记录）
 * - 提供折叠/展开交互
 * 
 * 【设计原则】
 * - 不包含业务逻辑，只负责展示
 * - 所有数据通过 props 接收
 * - 所有交互通过事件通知父组件
 * 
 * 【Props】
 * @prop {Array} sessions - 历史会话列表
 * @prop {Object} stats - 统计信息
 * @prop {boolean} isLoading - 是否正在加载列表
 * @prop {boolean} isLoadingDetail - 是否正在加载详情
 * @prop {string|number|null} expandedSessionId - 当前展开的会话 ID
 * @prop {Object|null} sessionDetail - 会话详情数据
 * 
 * 【Events】
 * @event refresh - 刷新历史记录
 * @event toggle-session - 切换会话展开状态（参数：sessionId）
 * 
 * 【UI 特性】
 * - 卡片式布局
 * - 折叠/展开动画
 * - 加载状态指示器
 * - 空状态提示
 */

// ========================================================================
// Props 定义
// ========================================================================

const props = defineProps({
  /** 
   * 历史会话列表
   * 每个会话包含：
   * - session_id: 会话唯一标识
   * - title: 会话标题
   * - created_at: 创建时间
   * - message_count: 消息数量
   * - summary: 会话摘要
   */
  sessions: {
    type: Array,
    required: true
  },
  
  /** 
   * 统计信息
   * 包含：
   * - total_sessions: 总会话数
   * - total_memory_items: 总记忆项数
   * - memory_types: 记忆类型分布
   */
  stats: {
    type: Object,
    required: true
  },
  
  /** 是否正在加载会话列表 */
  isLoading: {
    type: Boolean,
    default: false
  },
  
  /** 是否正在加载会话详情 */
  isLoadingDetail: {
    type: Boolean,
    default: false
  },
  
  /** 当前展开的会话 ID */
  expandedSessionId: {
    type: [String, Number, null],
    default: null
  },
  
  /** 
   * 会话详情数据
   * 包含：
   * - messages: 消息列表
   * - memories: 记忆项列表
   */
  sessionDetail: {
    type: Object,
    default: null
  }
})

// ========================================================================
// Events 定义
// ========================================================================

const emit = defineEmits([
  'refresh',         // 刷新历史记录
  'toggle-session'   // 切换会话展开状态
])

// ========================================================================
// 工具方法
// ========================================================================

/**
 * 格式化历史记录时间戳
 * 
 * @param {string|Date} timestamp - 时间戳
 * @returns {string} 格式化后的相对时间
 * 
 * 【格式规则】
 * - 1小时内：刚刚
 * - 24小时内：X 小时前
 * - 7天内：X 天前
 * - 更久：具体日期时间
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
 * 
 * @param {string|Date} timestamp - 时间戳
 * @returns {string} 格式化后的时间字符串（HH:MM:SS）
 * 
 * 【使用场景】会话详情中的消息时间显示
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
</script>

<template>
  <div class="flex-1 flex flex-col h-full bg-gray-50">
    <!-- 顶部工具栏 -->
    <div class="h-16 px-6 bg-white border-b border-gray-200 flex items-center justify-between shrink-0">
      <div class="flex items-center gap-4">
        <h2 class="font-bold text-gray-900 text-lg">历史记录</h2>
        <div class="flex items-center gap-2 text-sm">
          <span class="px-2 py-1 rounded-full bg-blue-50 text-blue-600 text-xs font-medium">
            <i class="fas fa-comments mr-1"></i>{{ stats.total_sessions }} 次对话
          </span>
          <span class="px-2 py-1 rounded-full bg-green-50 text-green-600 text-xs font-medium">
            <i class="fas fa-brain mr-1"></i>{{ stats.total_memory_items }} 条记忆
          </span>
        </div>
      </div>
      
      <div class="flex items-center gap-3">
        <!-- 刷新按钮 -->
        <button 
          @click="emit('refresh')"
          :disabled="isLoading"
          class="px-3 py-1.5 bg-blue-500 text-white rounded-lg text-sm hover:bg-blue-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          <i class="fas fa-sync" :class="{ 'animate-spin': isLoading }"></i>
          {{ isLoading ? '加载中...' : '刷新' }}
        </button>
      </div>
    </div>
    
    <!-- 主内容区域 -->
    <div class="flex-1 overflow-y-auto p-6">
      <!-- 加载状态 -->
      <div v-if="isLoading && sessions.length === 0" class="flex flex-col items-center justify-center h-full text-gray-400 py-20">
        <i class="fas fa-spinner fa-spin text-5xl mb-4"></i>
        <p class="text-lg font-medium">加载历史记录中...</p>
      </div>
      
      <!-- 空状态 -->
      <div v-else-if="sessions.length === 0" class="flex flex-col items-center justify-center h-full text-gray-400 py-20">
        <i class="fas fa-history text-5xl mb-4"></i>
        <p class="text-lg font-medium">暂无历史记录</p>
        <p class="text-sm mt-2">开始对话后，历史记录将显示在这里</p>
      </div>
      
      <!-- 会话列表 -->
      <div v-else class="max-w-4xl mx-auto space-y-4">
        <div 
          v-for="session in sessions" 
          :key="session.session_id"
          class="bg-white rounded-lg border border-gray-200 shadow-sm hover:shadow-md transition-shadow"
        >
          <!-- 会话头部 -->
          <div 
            @click="emit('toggle-session', session.session_id)"
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
</template>
