/**
 * 日志系统 Composable
 * =========================================================================
 * 
 * 【功能说明】
 * 封装后端日志的接收、存储、过滤和导出功能
 * 
 * 【使用场景】
 * - 实时接收 WebSocket 推送的后端日志
 * - 按级别和关键词过滤日志
 * - 导出日志用于调试
 * 
 * 【核心特性】
 * - 环形缓冲区（最多保存 1000 条）
 * - 实时过滤和搜索
 * - 日志暂停功能
 * - JSON 格式导出
 * 
 * @returns {Object} 日志相关状态和方法
 */

import { ref, computed, nextTick } from 'vue'

// ========================================================================
// 常量定义
// ========================================================================

/** @const {number} 最大日志条数（环形缓冲区大小） */
const MAX_LOGS = 1000

/**
 * 日志级别配置
 * 定义每个级别的显示样式和图标
 */
const LOG_LEVELS = {
  DEBUG: { 
    label: 'DEBUG', 
    color: 'text-gray-500', 
    bg: 'bg-gray-50', 
    icon: 'fa-bug' 
  },
  INFO: { 
    label: 'INFO', 
    color: 'text-blue-600', 
    bg: 'bg-blue-50', 
    icon: 'fa-info-circle' 
  },
  SUCCESS: { 
    label: 'SUCCESS', 
    color: 'text-green-600', 
    bg: 'bg-green-50', 
    icon: 'fa-check-circle' 
  },
  WARNING: { 
    label: 'WARNING', 
    color: 'text-yellow-600', 
    bg: 'bg-yellow-50', 
    icon: 'fa-exclamation-triangle' 
  },
  ERROR: { 
    label: 'ERROR', 
    color: 'text-red-600', 
    bg: 'bg-red-50', 
    icon: 'fa-times-circle' 
  }
}

export function useLogs() {
  // ========================================================================
  // 状态定义
  // ========================================================================
  
  /** @type {Ref<Array>} 日志列表（环形缓冲区） */
  const logs = ref([])
  
  /** @type {Ref<Object>} 日志过滤条件 */
  const logFilters = ref({
    levels: ['INFO', 'WARNING', 'ERROR'],  // 默认只显示这些级别
    search: ''                              // 搜索关键词
  })
  
  /** @type {Ref<boolean>} 是否暂停接收日志 */
  const logPaused = ref(false)
  
  /** @type {Ref<boolean>} 是否显示级别过滤下拉菜单 */
  const showLevelFilter = ref(false)
  
  /** @type {Ref<HTMLElement|null>} 日志容器 DOM 引用 */
  const logContainer = ref(null)
  
  /** @type {Ref<boolean>} 滚动条是否在底部 */
  const isLogScrollAtBottom = ref(true)
  
  // ========================================================================
  // 计算属性
  // ========================================================================
  
  /**
   * 日志统计信息
   * 
   * 【功能】实时统计各级别日志的数量
   * 【使用场景】在顶部工具栏显示统计徽章
   * 
   * @returns {Object} 统计结果
   * @returns {number} .total - 总日志数
   * @returns {number} .error - 错误日志数
   * @returns {number} .warning - 警告日志数
   * @returns {number} .info - 信息日志数
   */
  const logStats = computed(() => ({
    total: logs.value.length,
    error: logs.value.filter(l => l.level === 'ERROR').length,
    warning: logs.value.filter(l => l.level === 'WARNING').length,
    info: logs.value.filter(l => l.level === 'INFO').length
  }))
  
  /**
   * 过滤后的日志列表
   * 
   * 【功能】根据级别和搜索关键词过滤日志
   * 【过滤规则】
   * 1. 级别过滤：只显示选中级别的日志
   * 2. 关键词搜索：在消息、模块名、函数名中搜索
   * 
   * 【搜索范围】
   * - log.message：日志消息内容
   * - log.module：模块名称
   * - log.function：函数名称
   * 
   * @returns {Array} 过滤后的日志数组
   */
  const filteredLogs = computed(() => {
    return logs.value.filter(log => {
      // 级别过滤
      if (!logFilters.value.levels.includes(log.level)) return false
      
      // 关键词搜索（不区分大小写）
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
  
  // ========================================================================
  // 核心方法
  // ========================================================================
  
  /**
   * 添加日志条目
   * 
   * @param {Object} entry - 日志数据
   * @param {string} entry.level - 日志级别（DEBUG/INFO/WARNING/ERROR）
   * @param {string} entry.message - 日志消息
   * @param {string} [entry.module] - 模块名称
   * @param {string} [entry.function] - 函数名称
   * @param {number} [entry.line] - 行号
   * @param {string} [entry.trace] - 堆栈跟踪
   * 
   * 【功能】
   * - 接收并存储后端推送的日志
   * - 实现环形缓冲区（超过限制删除最旧的）
   * - 自动滚动到最新日志（如果用户在底部）
   * 
   * 【暂停机制】
   * - 如果日志已暂停，不添加新日志
   * - 用于方便用户查看历史日志
   */
  const addLog = (entry) => {
    // 暂停时不添加新日志
    if (logPaused.value) return
    
    logs.value.push({
      id: Date.now() + Math.random(),  // 唯一 ID
      timestamp: new Date(),            // 接收时间
      source: 'backend',                // 日志来源
      ...entry                          // 展开日志数据
    })
    
    // 【环形缓冲区】超过最大值时删除最旧的日志
    if (logs.value.length > MAX_LOGS) {
      logs.value.shift()
    }
    
    // 【自动滚动】只在用户位于底部时滚动
    nextTick(() => {
      if (isLogScrollAtBottom.value && logContainer.value) {
        scrollToBottom()
      }
    })
  }
  
  /**
   * 滚动到日志容器底部
   * 
   * 【功能】强制滚动到最新日志
   * 【调用时机】
   * - 添加新日志后（如果在底部）
   * - 用户点击"回到底部"按钮
   */
  const scrollToBottom = () => {
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight
    }
  }
  
  /**
   * 处理滚动事件
   * 
   * 【功能】检测用户是否滚动到底部
   * 【作用】决定是否自动滚动到新日志
   * 
   * 【判断逻辑】
   * - 距离底部小于 50px 视为在底部
   * - 在底部 → 自动滚动新日志
   * - 不在底部 → 不自动滚动（用户正在查看历史）
   */
  const handleScroll = () => {
    if (logContainer.value) {
      const { scrollTop, scrollHeight, clientHeight } = logContainer.value
      isLogScrollAtBottom.value = scrollHeight - scrollTop - clientHeight < 50
    }
  }
  
  /**
   * 切换日志级别过滤
   * 
   * @param {string} level - 日志级别
   * 
   * 【功能】添加/移除级别过滤条件
   * 【交互】点击级别复选框时调用
   */
  const toggleLevelFilter = (level) => {
    const index = logFilters.value.levels.indexOf(level)
    if (index > -1) {
      // 已选中 → 取消选中
      logFilters.value.levels.splice(index, 1)
    } else {
      // 未选中 → 添加选中
      logFilters.value.levels.push(level)
    }
  }
  
  /**
   * 清空所有日志
   * 
   * 【功能】删除所有日志记录
   * 【确认】需要用户确认操作
   * 【使用场景】日志过多需要清理时
   */
  const clearLogs = () => {
    if (confirm('确定要清空所有日志吗？')) {
      logs.value = []
    }
  }
  
  /**
   * 导出日志为 JSON 文件
   * 
   * 【功能】将过滤后的日志导出为 JSON 文件
   * 【文件名】logs_YYYY-MM-DDTHH-MM-SS.json
   * 
   * 【数据格式】
   * - 时间：ISO 格式完整时间
   * - 包含所有日志字段（级别、模块、函数、消息等）
   * - 中文字段名，方便查看
   * 
   * 【使用场景】
   * - 调试问题时需要保存日志
   * - 向开发者反馈问题
   */
  const exportLogs = () => {
    // 将日志转换为易读的格式
    const data = filteredLogs.value.map(log => ({
      时间: formatTime(log.timestamp, 'full'),
      级别: log.level,
      模块: log.module || '',
      函数: log.function || '',
      行号: log.line || '',
      消息: log.message,
      堆栈: log.trace || ''
    }))
    
    // 创建 Blob 和下载链接
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `logs_${new Date().toISOString().replace(/[:.]/g, '-')}.json`
    a.click()
    URL.revokeObjectURL(url)
  }
  
  /**
   * 格式化时间戳
   * 
   * @param {Date|string|number} timestamp - 时间戳
   * @param {string} format - 格式类型（'short' | 'full'）
   * @returns {string} 格式化后的时间字符串
   * 
   * 【格式说明】
   * - short: HH:MM:SS（显示在界面上）
   * - full: ISO 8601 格式（导出文件时使用）
   */
  const formatTime = (timestamp, format = 'short') => {
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
  
  // ========================================================================
  // 对外暴露
  // ========================================================================
  
  return {
    // 常量
    LOG_LEVELS,           // 日志级别配置
    MAX_LOGS,             // 最大日志数
    
    // 状态
    logs,                 // 日志列表
    logFilters,           // 过滤条件
    logPaused,            // 暂停状态
    showLevelFilter,      // 级别过滤菜单显示状态
    logContainer,         // 容器 DOM 引用
    isLogScrollAtBottom,  // 是否在底部
    
    // 计算属性
    logStats,             // 日志统计
    filteredLogs,         // 过滤后的日志
    
    // 方法
    addLog,               // 添加日志
    scrollToBottom,       // 滚动到底部
    handleScroll,         // 处理滚动事件
    toggleLevelFilter,    // 切换级别过滤
    clearLogs,            // 清空日志
    exportLogs,           // 导出日志
    formatTime            // 格式化时间
  }
}
