<script setup>
/**
 * 聊天主界面组件 - 顶层容器 (Top-Level Container)
 * =========================================================================
 * 
 * 【架构模式】Container/Presentational Pattern
 * 【组件层级】顶层协调组件
 * 
 * 【核心职责】
 * 1. 整合所有功能模块（聊天、历史、配置、日志）
 * 2. 管理全局 UI 状态（侧边栏、标签页）
 * 3. 协调子组件通信
 * 4. 懒加载数据（按需加载各模块数据）
 * 5. 集成 Live2D 角色展示
 * 
 * 【重构说明】
 * - 从原来的 1696 行单一组件重构为模块化架构
 * - 使用 Composables 封装复用逻辑
 * - 使用 Container 组件管理业务逻辑
 * - 使用 Presentational 组件负责 UI 展示
 * 
 * 【管理的模块】
 * - 聊天模块 (ChatContainer)
 * - 历史记录模块 (HistoryView)
 * - 系统配置模块 (ConfigEditor)
 * - 日志查看模块 (LogView)
 * - TTS 测试模块 (TTSTestPanel)
 * - ASR 测试模块 (ASRTestPanel)
 * - Live2D 角色 (Live2DCharacter)
 * 
 * 【数据流向】
 * - 父 → 子：通过 props 传递数据
 * - 子 → 父：通过 events 通知变化
 * - 跨组件：通过 Composables 共享状态
 * 
 * 【依赖的 Composables】
 * - useLogs: 日志系统
 * - useHistory: 历史记录
 * - useConfig: 系统配置
 * 
 * 【子组件】
 * - Sidebar: 侧边栏导航
 * - ChatContainer: 聊天容器（Smart Component）
 * - HistoryView: 历史记录视图（Dumb Component）
 * - ConfigEditor: 配置编辑器
 * - TTSTestPanel: TTS 测试面板
 * - ASRTestPanel: ASR 测试面板
 * - Live2DCharacter: Live2D 角色
 */

import { ref, onMounted } from 'vue'
import { useLogs } from '../../composables/useLogs'
import { useHistory } from '../../composables/useHistory'
import { useConfig } from '../../composables/useConfig'

import Sidebar from '../presentational/Sidebar.vue'
import ChatContainer from './ChatContainer.vue'
import HistoryView from '../presentational/HistoryView.vue'
import ConfigEditor from './ConfigEditor.vue'
import TTSTestPanel from '../panels/TTSTestPanel.vue'
import ASRTestPanel from '../panels/ASRTestPanel.vue'
import Live2DCharacter from '../presentational/Live2DCharacter.vue'

// ========================================================================
// Composables - 状态管理
// ========================================================================

/** 日志系统 Composable */
const logs = useLogs()

/** 历史记录 Composable */
const history = useHistory()

/** 系统配置 Composable */
const config = useConfig()

// ========================================================================
// UI 状态
// ========================================================================

/** 侧边栏显示状态 */
const showSidebar = ref(true)

/** 当前激活的标签页：chat（聊天）| history（历史）| settings（配置）| logs（日志） */
const activeTab = ref('chat')

/** Live2D 角色组件引用 */
const live2dCharacterRef = ref(null)

/** WebSocket 连接状态（从 ChatContainer 传递上来） */
const isConnected = ref(false)

// ========================================================================
// UI 交互方法
// ========================================================================

/**
 * 切换侧边栏显示/隐藏
 * 
 * 【功能】控制侧边栏在移动端的显示
 * 【触发】用户点击汉堡菜单图标
 */
const toggleSidebar = () => {
  showSidebar.value = !showSidebar.value
}

/**
 * 处理标签页切换
 * 
 * @param {string} tabId - 标签页 ID（chat/history/settings/logs）
 * 
 * 【功能】切换到指定标签页
 * 【懒加载策略】
 * - 首次进入历史页面：自动加载历史会话列表
 * - 首次进入配置页面：自动加载系统配置
 * - 优化性能：避免初始化时加载所有数据
 * 
 * 【错误处理】加载失败时显示友好提示
 */
const handleTabChange = (tabId) => {
  activeTab.value = tabId
  console.log('[UI] Tab changed to:', tabId)
  
  // 【懒加载】首次进入历史页面时自动加载数据
  if (tabId === 'history' && history.historySessions.value.length === 0) {
    console.log('[History] First time entering history tab, loading data...')
    history.loadSessions().catch(err => {
      console.error('[History] Failed to load sessions:', err)
    alert('加载历史记录失败，请稍后重试')
    })
  }
  
  // 【懒加载】首次进入配置页面时自动加载配置
  if (tabId === 'settings' && !config.systemConfig.value) {
    console.log('[Config] First time entering settings tab, loading config...')
    config.loadConfig().catch(err => {
      console.error('[Config] Failed to load config:', err)
      alert('加载配置失败，请稍后重试')
    })
  }
}

/**
 * 处理日志条目
 * 
 * @param {Object} logData - 日志数据对象
 * 
 * 【功能】接收从 ChatContainer 传递的日志
 * 【来源】后端通过 WebSocket 发送的日志
 * 【处理】添加到日志列表（由 useLogs 管理）
 */
const handleLogEntry = (logData) => {
  logs.addLog(logData)
}

// ========================================================================
// 生命周期钩子
// ========================================================================

/**
 * 组件挂载
 * 
 * 【初始化】
 * - 打印组件挂载日志
 * - 不预加载数据（采用懒加载策略）
 */
onMounted(() => {
  console.log('[ChatInterface] Component mounted - Ready to use')
  console.log('[Architecture] Using Container/Presentational Pattern')
})
</script>

<template>
  <!-- 主布局容器 -->
  <div class="flex w-full h-full md:h-[90vh] max-w-[1600px] bg-white md:rounded-2xl shadow-xl overflow-hidden border border-gray-200">
    
    <!-- 侧边栏 -->
    <Sidebar 
      :class="{'hidden md:flex': !showSidebar, 'flex': showSidebar}" 
      class="w-full md:w-80 shrink-0"
      :active-tab="activeTab"
      @tab-change="handleTabChange"
    />

    <!-- 右侧主内容区域 -->
    <div class="flex-1 flex flex-col h-full relative bg-gray-50">
      
      <!-- 聊天界面 -->
      <ChatContainer
        v-if="activeTab === 'chat'"
        :show-sidebar="showSidebar"
        @toggle-sidebar="toggleSidebar"
        @log-entry="handleLogEntry"
        @connection-change="(connected) => isConnected = connected"
      />

      <!-- 历史界面 -->
      <HistoryView
        v-if="activeTab === 'history'"
        :sessions="history.historySessions.value"
        :stats="history.historyStats.value"
        :is-loading="history.isLoadingHistory.value"
        :is-loading-detail="history.isLoadingDetail.value"
        :expanded-session-id="history.expandedSessionId.value"
        :session-detail="history.sessionDetail.value"
        @refresh="history.refresh"
        @toggle-session="history.toggleSessionDetail"
      />

      <!-- 配置界面 -->
      <div v-if="activeTab === 'settings'" class="flex-1 flex flex-col h-full bg-gray-50">
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
            <!-- 保存消息 -->
            <div v-if="config.configSaveMessage.value" 
                 class="px-3 py-1.5 rounded-lg text-sm font-medium"
                 :class="config.configSaveMessage.value.includes('成功') ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'">
              {{ config.configSaveMessage.value }}
            </div>

            <!-- 编辑配置按钮组 -->
            <template v-if="!config.isEditingConfig.value">
              <button 
                @click="config.startEdit"
                class="px-4 py-2 bg-blue-500 text-white rounded-lg text-sm hover:bg-blue-600 transition-colors flex items-center gap-2"
              >
                <i class="fas fa-edit"></i>
                编辑配置
              </button>
            </template>
            
            <template v-else>
              <button 
                @click="config.cancelEdit"
                :disabled="config.isSavingConfig.value"
                class="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg text-sm hover:bg-gray-300 transition-colors disabled:opacity-50"
              >
                取消
              </button>
              <button 
                @click="config.saveConfig"
                :disabled="config.isSavingConfig.value"
                class="px-4 py-2 bg-green-500 text-white rounded-lg text-sm hover:bg-green-600 transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                <i class="fas" :class="config.isSavingConfig.value ? 'fa-spinner fa-spin' : 'fa-save'"></i>
                {{ config.isSavingConfig.value ? '保存中...' : '保存' }}
              </button>
              <button 
                @click="config.resetConfig"
                :disabled="config.isSavingConfig.value"
                class="px-4 py-2 bg-red-500 text-white rounded-lg text-sm hover:bg-red-600 transition-colors disabled:opacity-50"
              >
                重置
              </button>
            </template>
            
            <!-- 刷新按钮 -->
            <button 
              @click="config.refresh"
              :disabled="config.isLoadingConfig.value"
              class="px-3 py-1.5 bg-blue-500 text-white rounded-lg text-sm hover:bg-blue-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              <i class="fas fa-sync" :class="{ 'animate-spin': config.isLoadingConfig.value }"></i>
              {{ config.isLoadingConfig.value ? '加载中...' : '刷新' }}
            </button>
          </div>
        </div>
        
        <!-- 主内容区域 -->
        <div class="flex-1 overflow-y-auto p-6">
          <!-- 加载状态 -->
          <div v-if="config.isLoadingConfig.value && !config.systemConfig.value" class="flex flex-col items-center justify-center h-full text-gray-400 py-20">
            <i class="fas fa-spinner fa-spin text-5xl mb-4"></i>
            <p class="text-lg font-medium">加载配置中...</p>
          </div>
          
          <!-- 错误状态 -->
          <div v-else-if="config.configLoadError.value" class="flex flex-col items-center justify-center h-full text-gray-400 py-20">
            <i class="fas fa-exclamation-triangle text-5xl mb-4 text-red-400"></i>
            <p class="text-lg font-medium text-red-600">加载配置失败</p>
            <p class="text-sm mt-2 text-gray-600">{{ config.configLoadError.value }}</p>
            <button 
              @click="config.refresh"
              class="mt-4 px-4 py-2 bg-blue-500 text-white rounded-lg text-sm hover:bg-blue-600 transition-colors flex items-center gap-2"
            >
              <i class="fas fa-redo"></i>
              重试
            </button>
          </div>
          
          <!-- 配置内容 -->
          <div v-else-if="config.systemConfig.value" class="max-w-5xl mx-auto space-y-6">
            <ConfigEditor 
              :config="config.systemConfig.value"
              :is-editing="config.isEditingConfig.value"
              :editing-config="config.editingConfig.value"
              @update="config.updateConfig"
              @test-tts="config.toggleTTSTest"
              @test-asr="config.toggleASRTest"
            />
          </div>
        </div>
      </div>

      <!-- 日志界面 -->
      <div v-if="activeTab === 'logs'" class="flex-1 flex flex-col h-full bg-gray-50">
        <!-- 顶部工具栏 -->
        <div class="h-16 px-6 bg-white border-b border-gray-200 flex items-center justify-between shrink-0">
          <div class="flex items-center gap-4">
            <h2 class="font-bold text-gray-900 text-lg">系统日志</h2>
            <div class="flex items-center gap-2 text-sm">
              <span class="px-2 py-1 rounded-full bg-red-50 text-red-600 text-xs font-medium">
                <i class="fas fa-times-circle mr-1"></i>{{ logs.logStats.value.error }}
              </span>
              <span class="px-2 py-1 rounded-full bg-yellow-50 text-yellow-600 text-xs font-medium">
                <i class="fas fa-exclamation-triangle mr-1"></i>{{ logs.logStats.value.warning }}
              </span>
              <span class="px-2 py-1 rounded-full bg-blue-50 text-blue-600 text-xs font-medium">
                <i class="fas fa-info-circle mr-1"></i>{{ logs.logStats.value.info }}
              </span>
            </div>
          </div>
          
          <div class="flex items-center gap-3">
            <!-- 搜索框 -->
            <div class="relative">
              <i class="fas fa-search absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-xs"></i>
              <input 
                v-model="logs.logFilters.value.search"
                type="text"
                placeholder="搜索日志..."
                class="pl-9 pr-4 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 w-48"
              />
            </div>
            
            <!-- 级别过滤下拉菜单 -->
            <div class="relative">
              <button 
                @click="logs.showLevelFilter.value = !logs.showLevelFilter.value"
                class="px-3 py-1.5 border border-gray-300 rounded-lg text-sm hover:bg-gray-50 flex items-center gap-2"
              >
                <i class="fas fa-filter"></i>
                <span>级别</span>
                <i class="fas fa-chevron-down text-xs"></i>
              </button>
              
              <!-- 下拉面板 -->
              <div v-if="logs.showLevelFilter.value" class="absolute top-full right-0 mt-2 bg-white border border-gray-200 rounded-lg shadow-lg p-2 z-10 min-w-[160px]">
                <div v-for="(levelConfig, level) in logs.LOG_LEVELS" :key="level" class="flex items-center gap-2 p-2 hover:bg-gray-50 rounded cursor-pointer">
                  <input 
                    type="checkbox" 
                    :checked="logs.logFilters.value.levels.includes(level)"
                    @change="logs.toggleLevelFilter(level)"
                    class="rounded text-blue-500"
                  />
                  <i class="fas text-sm" :class="[levelConfig.icon, levelConfig.color]"></i>
                  <span class="text-sm">{{ levelConfig.label }}</span>
                </div>
              </div>
            </div>
            
            <!-- 清空日志 -->
            <button 
              @click="logs.clearLogs"
              class="px-3 py-1.5 border border-gray-300 rounded-lg text-sm hover:bg-red-50 hover:border-red-300 hover:text-red-600 transition-colors"
            >
              <i class="fas fa-trash mr-1"></i>清空
            </button>
            
            <!-- 导出日志 -->
            <button 
              @click="logs.exportLogs"
              class="px-3 py-1.5 bg-blue-500 text-white rounded-lg text-sm hover:bg-blue-600 transition-colors"
            >
              <i class="fas fa-download mr-1"></i>导出
            </button>
            
            <!-- 暂停/继续 -->
            <button 
              @click="logs.logPaused.value = !logs.logPaused.value"
              class="w-9 h-9 rounded-full flex items-center justify-center border border-gray-300 hover:bg-gray-50 transition-colors"
              :class="logs.logPaused.value ? 'bg-yellow-50 border-yellow-300 text-yellow-600' : 'text-gray-600'"
              :title="logs.logPaused.value ? '继续日志' : '暂停日志'"
            >
              <i class="fas text-sm" :class="logs.logPaused.value ? 'fa-play' : 'fa-pause'"></i>
            </button>
          </div>
        </div>
        
        <!-- 日志列表主体 -->
        <div 
          ref="logs.logContainer"
          @scroll="logs.handleScroll"
          class="flex-1 overflow-y-auto p-4 space-y-2 font-mono text-xs"
        >
          <div 
            v-for="log in logs.filteredLogs.value" 
            :key="log.id"
            class="flex items-start gap-3 p-3 bg-white border border-gray-200 rounded-lg hover:shadow-sm transition-shadow"
            :class="logs.LOG_LEVELS[log.level]?.bg"
          >
            <!-- 左侧时间 & 级别 -->
            <div class="shrink-0 w-24">
              <div class="text-gray-500 text-[10px] mb-1">{{ logs.formatTime(log.timestamp) }}</div>
              <div class="flex items-center gap-1" :class="logs.LOG_LEVELS[log.level]?.color">
                <i class="fas text-xs" :class="logs.LOG_LEVELS[log.level]?.icon"></i>
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
          <div v-if="logs.filteredLogs.value.length === 0" class="flex flex-col items-center justify-center h-full text-gray-400 py-20">
            <i class="fas fa-inbox text-5xl mb-4"></i>
            <p class="text-lg font-medium">暂无日志</p>
            <p class="text-sm mt-2">{{ logs.logs.value.length > 0 ? '当前过滤条件没有匹配的日志' : '等待系统生成日志...' }}</p>
          </div>
        </div>
        
        <!-- 底部状态栏 -->
        <div class="h-10 px-6 bg-white border-t border-gray-200 flex items-center justify-between text-xs text-gray-500 shrink-0">
          <div class="flex items-center gap-4">
            <span>显示 {{ logs.filteredLogs.value.length }} / {{ logs.logs.value.length }} 条日志</span>
            <span v-if="logs.logPaused.value" class="text-yellow-600 font-medium">
              <i class="fas fa-pause-circle mr-1"></i>已暂停
            </span>
          </div>
          <div class="text-gray-400">
            <i class="fas fa-info-circle mr-1"></i>环形缓冲区最多保留 {{ logs.MAX_LOGS }} 条
          </div>
        </div>
      </div>
    </div>
  </div>
  
  <!-- TTS 测试弹窗 -->
  <TTSTestPanel v-if="config.showTTSTest.value" @close="config.showTTSTest.value = false" />
  
  <!-- ASR 测试弹窗 -->
  <ASRTestPanel v-if="config.showASRTest.value" @close="config.showASRTest.value = false" />
  
  <!-- Live2D 角色 -->
  <Live2DCharacter
    v-if="config.live2dEnabled.value"
    ref="live2dCharacterRef"
    :model-path="'/live2d/Pio/model.json'"
    :width="300"
    :height="400"
    :scale="0.3"
    state="idle"
    :enable-mouse-tracking="true"
    :enable-click="true"
    :enable-drag="false"
    class="fixed z-50 pointer-events-auto"
    :style="{
      left: `${config.live2dPosition.value.x}px`,
      top: `${config.live2dPosition.value.y}px`
    }"
  />
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
