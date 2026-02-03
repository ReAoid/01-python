/**
 * WebSocket 连接管理 Composable
 * =========================================================================
 * 
 * 【功能说明】
 * 封装 WebSocket 连接、消息处理、自动重连逻辑
 * 
 * 【使用场景】
 * - 实时聊天消息收发
 * - TTS 音频流接收
 * - 后端状态同步
 * 
 * 【核心特性】
 * - 自动重连机制（3秒间隔）
 * - 支持文本和二进制数据
 * - 自动清理资源
 * 
 * @returns {Object} WebSocket 相关状态和方法
 */

import { ref, onUnmounted } from 'vue'

export function useWebSocket() {
  // ========================================================================
  // 状态定义
  // ========================================================================
  
  /** @type {Ref<WebSocket|null>} WebSocket 实例 */
  const socket = ref(null)
  
  /** @type {Ref<boolean>} 连接状态 */
  const isConnected = ref(false)
  
  /** @type {Ref<number|null>} 重连定时器 ID */
  const reconnectInterval = ref(null)
  
  // 消息处理回调函数（不使用 ref，避免响应式开销）
  let messageHandler = null  // 文本消息处理函数
  let audioHandler = null    // 音频数据处理函数
  
  // ========================================================================
  // 核心方法
  // ========================================================================
  
  /**
   * 连接 WebSocket 服务器
   * 
   * @param {Function} onMessage - 文本消息处理回调
   * @param {Function} onAudio - 音频数据处理回调
   * 
   * 【连接流程】
   * 1. 根据当前协议选择 ws 或 wss
   * 2. 开发环境连接 localhost:8000，生产环境使用当前 host
   * 3. 建立连接并注册事件监听器
   * 4. 连接成功后清除重连定时器
   */
  const connect = (onMessage, onAudio) => {
    // 保存回调函数，用于重连时复用
    messageHandler = onMessage
    audioHandler = onAudio
    
    // 根据当前页面协议选择 WebSocket 协议
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    
    // 根据环境选择主机地址
    const wsHost = import.meta.env.DEV ? 'localhost:8000' : window.location.host
    
    // 构建完整的 WebSocket URL
    const wsUrl = `${wsProtocol}//${wsHost}/ws/chat`

    // 创建 WebSocket 连接
    socket.value = new WebSocket(wsUrl)

    /**
     * 连接成功事件处理
     * - 更新连接状态
     * - 清除重连定时器
     */
    socket.value.onopen = () => {
      console.log('[WebSocket] Connected')
      isConnected.value = true
      
      // 连接成功后清除重连定时器
      if (reconnectInterval.value) {
        clearInterval(reconnectInterval.value)
        reconnectInterval.value = null
      }
    }

    /**
     * 消息接收事件处理
     * 
     * 【支持的数据类型】
     * 1. 字符串（JSON）：聊天消息、状态更新
     * 2. ArrayBuffer/Blob：TTS 音频流
     */
    socket.value.onmessage = async (event) => {
      // 处理文本消息（JSON 格式）
      if (typeof event.data === 'string') {
        try {
          const message = JSON.parse(event.data)
          if (messageHandler) messageHandler(message)
        } catch (e) {
          console.error('[WebSocket] Failed to parse message:', e)
        }
      } 
      // 处理二进制数据（音频流）
      else if (event.data instanceof ArrayBuffer || event.data instanceof Blob) {
        if (audioHandler) {
          let arrayBuffer
          
          // Blob 需要先转换为 ArrayBuffer
          if (event.data instanceof Blob) {
            arrayBuffer = await event.data.arrayBuffer()
          } else {
            arrayBuffer = event.data
          }
          
          audioHandler(arrayBuffer)
        }
      }
    }

    /**
     * 连接关闭事件处理
     * 
     * 【自动重连机制】
     * - 连接断开后自动尝试重连
     * - 重连间隔：3秒
     * - 避免重复创建定时器
     */
    socket.value.onclose = () => {
      console.log('[WebSocket] Disconnected')
      isConnected.value = false
      
      // 启动自动重连（避免重复创建定时器）
      if (!reconnectInterval.value) {
        reconnectInterval.value = setInterval(() => {
          console.log('[WebSocket] Attempting to reconnect...')
          connect(messageHandler, audioHandler)
        }, 3000)  // 每 3 秒尝试重连一次
      }
    }

    /**
     * 错误事件处理
     */
    socket.value.onerror = (error) => {
      console.error('[WebSocket] Error:', error)
    }
  }
  
  /**
   * 发送文本消息
   * 
   * @param {string|Object} data - 要发送的数据（字符串或对象）
   * @returns {boolean} 是否发送成功
   * 
   * 【数据处理】
   * - 字符串：直接发送
   * - 对象：自动序列化为 JSON
   */
  const send = (data) => {
    // 检查连接状态
    if (socket.value && socket.value.readyState === WebSocket.OPEN) {
      if (typeof data === 'string') {
        socket.value.send(data)
      } else {
        // 对象自动序列化为 JSON
        socket.value.send(JSON.stringify(data))
      }
      return true
    }
    return false
  }
  
  /**
   * 发送二进制数据
   * 
   * @param {ArrayBuffer|Blob} data - 二进制数据
   * @returns {boolean} 是否发送成功
   * 
   * 【使用场景】
   * - 发送录音数据（ASR）
   * - 发送文件
   */
  const sendBinary = (data) => {
    if (socket.value && socket.value.readyState === WebSocket.OPEN) {
      socket.value.send(data)
      return true
    }
    return false
  }
  
  /**
   * 断开 WebSocket 连接
   * 
   * 【清理工作】
   * - 关闭 WebSocket 连接
   * - 清除重连定时器
   */
  const disconnect = () => {
    // 关闭 WebSocket 连接
    if (socket.value) {
      socket.value.close()
    }
    
    // 清除重连定时器
    if (reconnectInterval.value) {
      clearInterval(reconnectInterval.value)
      reconnectInterval.value = null
    }
  }
  
  // ========================================================================
  // 生命周期钩子
  // ========================================================================
  
  /**
   * 组件卸载时自动清理资源
   * 防止内存泄漏
   */
  onUnmounted(() => {
    disconnect()
  })
  
  // ========================================================================
  // 对外暴露
  // ========================================================================
  
  return {
    socket,          // WebSocket 实例
    isConnected,     // 连接状态
    connect,         // 连接方法
    send,            // 发送文本消息
    sendBinary,      // 发送二进制数据
    disconnect       // 断开连接
  }
}
