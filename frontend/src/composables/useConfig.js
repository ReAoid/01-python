/**
 * 配置管理 Composable
 * =========================================================================
 * 
 * 【功能说明】
 * 封装系统配置的读取、编辑、保存和重置功能
 * 
 * 【管理的配置】
 * - LLM 配置（模型、API密钥等）
 * - TTS/ASR 配置
 * - 用户信息配置
 * - Live2D 模型配置
 * - 系统参数配置
 * 
 * 【核心特性】
 * - 配置编辑模式（防止意外修改）
 * - 实时保存反馈
 * - 配置重置功能
 * - Live2D 状态同步
 * 
 * @returns {Object} 配置相关状态和方法
 */

import { ref } from 'vue'

export function useConfig() {
  // ========================================================================
  // 状态定义
  // ========================================================================
  
  /** @type {Ref<Object|null>} 当前系统配置 */
  const systemConfig = ref(null)
  
  /** @type {Ref<boolean>} 是否正在加载配置 */
  const isLoadingConfig = ref(false)
  
  /** @type {Ref<string|null>} 配置加载错误信息 */
  const configLoadError = ref(null)
  
  /** @type {Ref<boolean>} 是否处于编辑模式 */
  const isEditingConfig = ref(false)
  
  /** @type {Ref<boolean>} 是否正在保存配置 */
  const isSavingConfig = ref(false)
  
  /** @type {Ref<string>} 保存结果消息 */
  const configSaveMessage = ref('')
  
  /** @type {Ref<Object|null>} 编辑中的配置副本 */
  const editingConfig = ref(null)
  
  // Live2D 相关状态（用于实时控制）
  /** @type {Ref<boolean>} Live2D 是否启用 */
  const live2dEnabled = ref(false)
  
  /** @type {Ref<Object>} Live2D 模型位置 */
  const live2dPosition = ref({ x: 100, y: 500 })
  
  // 测试面板状态
  /** @type {Ref<boolean>} 是否显示 TTS 测试面板 */
  const showTTSTest = ref(false)
  
  /** @type {Ref<boolean>} 是否显示 ASR 测试面板 */
  const showASRTest = ref(false)
  
  // ========================================================================
  // 核心方法
  // ========================================================================
  
  /**
   * 加载系统配置
   * 
   * 【功能】从后端 API 获取当前系统配置
   * 【API】GET /api/config/current
   * 
   * 【返回数据结构】
   * - chat_llm: LLM 配置（模型、API等）
   * - tts: TTS 配置
   * - asr: ASR 配置
   * - user_profile: 用户信息
   * - live2d: Live2D 模型配置
   * - system: 系统参数
   * 
   * 【状态同步】
   * - 加载成功后同步 Live2D 状态
   * - 用于实时控制 Live2D 模型显示
   * 
   * @throws {Error} API 请求失败时抛出异常
   */
  const loadConfig = async () => {
    // 防止重复加载
    if (isLoadingConfig.value) return
    
    isLoadingConfig.value = true
    configLoadError.value = null
    
    try {
      const response = await fetch('/api/config/current')
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      const data = await response.json()
      systemConfig.value = data
      
      // 【重要】更新 Live2D 状态，用于实时控制
      if (data.live2d) {
        live2dEnabled.value = data.live2d.enabled || false
        if (data.live2d.position) {
          live2dPosition.value = {
            x: data.live2d.position.x || 100,
            y: data.live2d.position.y || 500
          }
        }
      }
      
      console.log('[Config] Loaded system config:', data)
    } catch (error) {
      console.error('[Config] Failed to load system config:', error)
      configLoadError.value = error.message || '加载配置失败'
      throw error
    } finally {
      isLoadingConfig.value = false
    }
  }
  
  /**
   * 开始编辑配置
   * 
   * 【功能】进入编辑模式
   * 【流程】
   * 1. 创建当前配置的深拷贝
   * 2. 切换到编辑模式
   * 3. 确保必需的配置项存在
   * 
   * 【为什么深拷贝】
   * - 避免修改原始配置对象
   * - 取消时可以恢复原始值
   * 
   * 【配置完整性检查】
   * - 确保 live2d 配置存在
   * - 提供默认值
   */
  const startEdit = () => {
    isEditingConfig.value = true
    
    // 深拷贝当前配置（防止直接修改原对象）
    editingConfig.value = JSON.parse(JSON.stringify(systemConfig.value))
    
    // 【配置完整性】确保 live2d 配置存在
    if (!editingConfig.value.live2d) {
      editingConfig.value.live2d = {
        enabled: false,
        position: {
          x: 100,
          y: 500,
          max_x: 1920,
          max_y: 1080
        }
      }
    }
  }
  
  /**
   * 取消编辑
   * 
   * 【功能】退出编辑模式，丢弃所有修改
   * 【清理工作】
   * - 清除编辑副本
   * - 清除保存消息
   * - 退出编辑模式
   */
  const cancelEdit = () => {
    isEditingConfig.value = false
    editingConfig.value = null
    configSaveMessage.value = ''
  }
  
  /**
   * 保存配置
   * 
   * 【功能】将编辑后的配置保存到后端
   * 【API】PUT /api/config/update
   * 
   * 【流程】
   * 1. 发送编辑后的配置到后端
   * 2. 后端验证并保存
   * 3. 更新本地配置为最新值
   * 4. 同步 Live2D 状态
   * 5. 退出编辑模式
   * 
   * 【用户反馈】
   * - 成功：显示 "保存成功！"（3秒后自动消失）
   * - 失败：显示错误信息（不自动消失）
   * 
   * @throws {Error} API 请求失败时抛出异常
   */
  const saveConfig = async () => {
    isSavingConfig.value = true
    configSaveMessage.value = ''
    
    try {
      const response = await fetch('/api/config/update', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(editingConfig.value)
      })
      
      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || '保存失败')
      }
      
      const result = await response.json()
      
      configSaveMessage.value = '保存成功！'
      isEditingConfig.value = false
      
      // 【重要】更新本地配置为后端返回的最新值
      systemConfig.value = result.config
      
      // 【实时同步】更新 Live2D 状态
      if (result.config.live2d) {
        live2dEnabled.value = result.config.live2d.enabled || false
        if (result.config.live2d.position) {
          live2dPosition.value = {
            x: result.config.live2d.position.x || 100,
            y: result.config.live2d.position.y || 500
          }
        }
      }
      
      // 3秒后自动清除成功消息
      setTimeout(() => {
        configSaveMessage.value = ''
      }, 3000)
    } catch (error) {
      console.error('[Config] Failed to save config:', error)
      configSaveMessage.value = `保存失败: ${error.message}`
      throw error
    } finally {
      isSavingConfig.value = false
    }
  }
  
  /**
   * 重置配置到默认值
   * 
   * 【功能】将所有配置恢复到系统默认值
   * 【API】POST /api/config/reset
   * 
   * 【重要提示】
   * - 此操作不可撤销
   * - 需要用户确认
   * - 清除所有自定义配置
   * 
   * 【使用场景】
   * - 配置错误导致系统异常
   * - 需要恢复出厂设置
   * 
   * @throws {Error} API 请求失败时抛出异常
   */
  const resetConfig = async () => {
    // 【用户确认】防止误操作
    if (!confirm('确定要重置所有配置到默认值吗？此操作不可撤销。')) {
      return
    }
    
    isSavingConfig.value = true
    configSaveMessage.value = ''
    
    try {
      const response = await fetch('/api/config/reset', {
        method: 'POST'
      })
      
      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || '重置失败')
      }
      
      const result = await response.json()
      
      configSaveMessage.value = '配置已重置！'
      isEditingConfig.value = false
      
      // 更新为默认配置
      systemConfig.value = result.config
      editingConfig.value = null
      
      // 3秒后清除消息
      setTimeout(() => {
        configSaveMessage.value = ''
      }, 3000)
    } catch (error) {
      console.error('[Config] Failed to reset config:', error)
      configSaveMessage.value = `重置失败: ${error.message}`
      throw error
    } finally {
      isSavingConfig.value = false
    }
  }
  
  /**
   * 刷新配置
   * 
   * 【功能】重新从后端加载最新配置
   * 【调用时机】用户点击刷新按钮
   */
  const refresh = async () => {
    await loadConfig()
  }
  
  /**
   * 更新配置（内部使用）
   * 
   * @param {Object} newConfig - 新的配置对象
   * 
   * 【功能】直接更新配置对象
   * 【使用场景】子组件需要更新配置时的回调
   */
  const updateConfig = (newConfig) => {
    systemConfig.value = newConfig
  }
  
  /**
   * 切换 TTS 测试面板显示状态
   * 
   * 【功能】打开/关闭 TTS 测试弹窗
   * 【互斥规则】打开 TTS 测试时自动关闭 ASR 测试
   * 
   * 【使用场景】
   * - 用户点击 "测试 TTS" 按钮
   * - 测试 TTS 配置是否正常
   */
  const toggleTTSTest = () => {
    showTTSTest.value = !showTTSTest.value
    
    // 互斥：只能同时显示一个测试面板
    if (showTTSTest.value) {
      showASRTest.value = false
    }
  }
  
  /**
   * 切换 ASR 测试面板显示状态
   * 
   * 【功能】打开/关闭 ASR 测试弹窗
   * 【互斥规则】打开 ASR 测试时自动关闭 TTS 测试
   * 
   * 【使用场景】
   * - 用户点击 "测试 ASR" 按钮
   * - 测试 ASR 配置是否正常
   */
  const toggleASRTest = () => {
    showASRTest.value = !showASRTest.value
    
    // 互斥：只能同时显示一个测试面板
    if (showASRTest.value) {
      showTTSTest.value = false
    }
  }
  
  // ========================================================================
  // 对外暴露
  // ========================================================================
  
  return {
    // 配置状态
    systemConfig,         // 当前系统配置
    isLoadingConfig,      // 加载状态
    configLoadError,      // 加载错误
    isEditingConfig,      // 编辑模式
    isSavingConfig,       // 保存状态
    configSaveMessage,    // 保存消息
    editingConfig,        // 编辑中的配置
    
    // Live2D 状态
    live2dEnabled,        // 是否启用
    live2dPosition,       // 模型位置
    
    // 测试面板状态
    showTTSTest,          // TTS 测试面板
    showASRTest,          // ASR 测试面板
    
    // 配置管理方法
    loadConfig,           // 加载配置
    startEdit,            // 开始编辑
    cancelEdit,           // 取消编辑
    saveConfig,           // 保存配置
    resetConfig,          // 重置配置
    refresh,              // 刷新配置
    updateConfig,         // 更新配置
    
    // 测试面板方法
    toggleTTSTest,        // 切换 TTS 测试
    toggleASRTest         // 切换 ASR 测试
  }
}
