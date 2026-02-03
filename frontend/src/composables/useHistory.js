/**
 * 历史记录功能 Composable
 * =========================================================================
 * 
 * 【功能说明】
 * 封装聊天历史记录的数据管理和 API 交互逻辑
 * 
 * 【使用场景】
 * - 查看历史会话列表
 * - 查看会话详情和消息记录
 * - 统计历史数据
 * 
 * 【核心特性】
 * - 懒加载（首次进入页面时才加载数据）
 * - 会话详情折叠/展开
 * - 统计信息展示
 * 
 * @returns {Object} 历史记录相关状态和方法
 */

import { ref } from 'vue'

export function useHistory() {
  // ========================================================================
  // 状态定义
  // ========================================================================
  
  /** @type {Ref<Array>} 历史会话列表 */
  const historySessions = ref([])
  
  /** @type {Ref<string|null>} 当前选中的会话 ID */
  const selectedSession = ref(null)
  
  /** @type {Ref<Object|null>} 会话详情数据 */
  const sessionDetail = ref(null)
  
  /** @type {Ref<Object>} 历史统计信息 */
  const historyStats = ref({
    total_sessions: 0,      // 总会话数
    total_memory_items: 0,  // 总记忆项数
    memory_types: {}        // 记忆类型统计
  })
  
  /** @type {Ref<boolean>} 是否正在加载历史列表 */
  const isLoadingHistory = ref(false)
  
  /** @type {Ref<boolean>} 是否正在加载会话详情 */
  const isLoadingDetail = ref(false)
  
  /** @type {Ref<string|null>} 当前展开的会话 ID */
  const expandedSessionId = ref(null)
  
  // ========================================================================
  // 核心方法
  // ========================================================================
  
  /**
   * 加载历史会话列表
   * 
   * 【功能】从后端 API 获取历史会话列表
   * 【防抖】如果正在加载中，直接返回（防止重复请求）
   * 
   * 【API】GET /api/history/sessions?count=10
   * 【返回】会话数组，包含会话 ID、标题、时间等
   * 
   * @throws {Error} API 请求失败时抛出异常
   */
  const loadSessions = async () => {
    // 防止重复加载
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
      await loadStatistics()
      
      console.log('[History] Loaded sessions:', data.length)
    } catch (error) {
      console.error('[History] Failed to load sessions:', error)
      throw error
    } finally {
      isLoadingHistory.value = false
    }
  }
  
  /**
   * 加载会话详情
   * 
   * @param {string} sessionId - 会话 ID
   * 
   * 【功能】获取指定会话的完整消息记录
   * 【API】GET /api/history/session/{sessionId}
   * 【返回】会话详情，包含所有消息、记忆项等
   * 
   * 【状态更新】
   * - sessionDetail: 详情数据
   * - selectedSession: 当前选中的会话 ID
   * - expandedSessionId: 展开的会话 ID
   * 
   * @throws {Error} API 请求失败时抛出异常
   */
  const loadSessionDetail = async (sessionId) => {
    // 防止重复加载
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
      throw error
    } finally {
      isLoadingDetail.value = false
    }
  }
  
  /**
   * 加载统计信息
   * 
   * 【功能】获取历史记录的统计数据
   * 【API】GET /api/history/statistics
   * 【返回】
   * - total_sessions: 总会话数
   * - total_memory_items: 总记忆项数
   * - memory_types: 记忆类型分布
   * 
   * 【错误处理】
   * - 即使失败也不抛出异常，只记录日志
   * - 不影响主功能的使用
   */
  const loadStatistics = async () => {
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
      // 不抛出异常，允许继续使用
    }
  }
  
  /**
   * 切换会话详情展开状态
   * 
   * @param {string} sessionId - 会话 ID
   * 
   * 【功能】折叠/展开会话详情
   * 【交互逻辑】
   * - 如果点击的是已展开的会话 → 折叠（清空数据）
   * - 如果点击的是其他会话 → 展开（加载详情）
   * 
   * 【使用场景】用户点击会话卡片时
   */
  const toggleSessionDetail = async (sessionId) => {
    if (expandedSessionId.value === sessionId) {
      // 折叠当前会话
      expandedSessionId.value = null
      selectedSession.value = null
      sessionDetail.value = null
    } else {
      // 展开新会话
      await loadSessionDetail(sessionId)
    }
  }
  
  /**
   * 刷新历史记录
   * 
   * 【功能】重新加载会话列表和统计信息
   * 【调用时机】用户点击刷新按钮
   */
  const refresh = async () => {
    await loadSessions()
  }
  
  // ========================================================================
  // 对外暴露
  // ========================================================================
  
  return {
    // 状态
    historySessions,      // 会话列表
    selectedSession,      // 选中的会话 ID
    sessionDetail,        // 会话详情数据
    historyStats,         // 统计信息
    isLoadingHistory,     // 列表加载状态
    isLoadingDetail,      // 详情加载状态
    expandedSessionId,    // 展开的会话 ID
    
    // 方法
    loadSessions,         // 加载会话列表
    loadSessionDetail,    // 加载会话详情
    loadStatistics,       // 加载统计信息
    toggleSessionDetail,  // 切换详情展开
    refresh               // 刷新数据
  }
}
