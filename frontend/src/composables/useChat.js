/**
 * 聊天功能 Composable
 * =========================================================================
 * 
 * 【功能说明】
 * 封装聊天相关的状态管理和消息处理逻辑
 * 
 * 【使用场景】
 * - 管理聊天消息列表
 * - 处理用户输入和 AI 回复
 * - 控制聊天界面滚动
 * 
 * 【核心特性】
 * - 支持流式输出（AI 消息逐字显示）
 * - 自动滚动到最新消息
 * - 区分消息完成状态
 * 
 * @returns {Object} 聊天相关状态和方法
 */

import { ref, nextTick } from 'vue'

export function useChat() {
  // ========================================================================
  // 状态定义
  // ========================================================================
  
  /** @type {Ref<Array>} 消息列表 */
  const messages = ref([])
  
  /** @type {Ref<string>} 用户输入内容 */
  const userInput = ref('')
  
  /** @type {Ref<boolean>} AI 是否正在输入 */
  const isTyping = ref(false)
  
  /** @type {Ref<HTMLElement|null>} 聊天容器 DOM 引用 */
  const chatContainer = ref(null)
  
  /** @type {Ref<string>} AI 角色名称 */
  const characterName = ref('灵依')
  
  /** @type {Ref<string>} 初始欢迎消息 */
  const initialMessage = ref('你好！我是你的私人AI助手。有什么我可以帮你的吗？')
  
  // ========================================================================
  // 核心方法
  // ========================================================================
  
  /**
   * 初始化消息列表
   * 
   * 【功能】创建包含初始欢迎消息的消息列表
   * 【调用时机】组件挂载时 / 清空消息时
   */
  const initMessages = () => {
    messages.value = [
      {
        id: 1,                    // 消息唯一标识
        role: 'ai',               // 消息角色：ai / user
        content: initialMessage.value,  // 消息内容
        timestamp: new Date().toLocaleTimeString([], { 
          hour: '2-digit', 
          minute: '2-digit' 
        }),                       // 时间戳（显示用）
        type: 'text'              // 消息类型：text / image / audio
      }
    ]
  }
  
  /**
   * 添加用户消息
   * 
   * @param {string} content - 用户输入的消息内容
   * @returns {Object} 创建的消息对象
   * 
   * 【功能】
   * - 创建用户消息并添加到消息列表
   * - 标记上一条 AI 消息为完成状态（防止继续追加）
   * 
   * 【使用场景】
   * - 用户点击发送按钮
   * - 用户按下回车键
   */
  const addUserMessage = (content) => {
    const message = {
      id: Date.now(),           // 使用时间戳作为唯一 ID
      role: 'user',
      content: content,
      timestamp: new Date().toLocaleTimeString([], { 
        hour: '2-digit', 
        minute: '2-digit' 
      }),
      type: 'text'
    }
    
    messages.value.push(message)
    
    // 【重要】标记上一条 AI 消息为已完成
    // 防止新的 AI 回复追加到旧消息上
    const lastMessage = messages.value[messages.value.length - 2]
    if (lastMessage && lastMessage.role === 'ai') {
      lastMessage.isComplete = true
    }
    
    return message
  }
  
  /**
   * 添加或更新 AI 消息
   * 
   * @param {string} content - AI 返回的消息内容（可能是片段）
   * 
   * 【功能】支持流式输出
   * - 如果最后一条是未完成的 AI 消息，则追加内容
   * - 否则创建新的 AI 消息
   * 
   * 【使用场景】
   * - WebSocket 接收到 AI 的流式回复
   * - 每接收到一个文本片段调用一次
   * 
   * 【示例】
   * addOrUpdateAIMessage('你') 
   * addOrUpdateAIMessage('好')  // 追加到上一条，显示 "你好"
   * addOrUpdateAIMessage('！')  // 追加到上一条，显示 "你好！"
   */
  const addOrUpdateAIMessage = (content) => {
    const lastMessage = messages.value[messages.value.length - 1]
    
    // 判断是否应该追加到现有消息
    if (lastMessage && lastMessage.role === 'ai' && !lastMessage.isComplete) {
      // 流式追加内容
      lastMessage.content += content
    } else {
      // 创建新消息
      messages.value.push({
        id: Date.now(),
        role: 'ai',
        content: content,
        timestamp: new Date().toLocaleTimeString([], { 
          hour: '2-digit', 
          minute: '2-digit' 
        }),
        type: 'text',
        isComplete: false     // 标记为未完成，允许后续追加
      })
    }
  }
  
  /**
   * 滚动到聊天容器底部
   * 
   * 【功能】自动滚动到最新消息
   * 【调用时机】
   * - 添加新消息后
   * - 更新消息内容后
   * 
   * 【技术要点】
   * - 使用 nextTick 确保 DOM 更新完成后再滚动
   * - 直接设置 scrollTop 为 scrollHeight
   */
  const scrollToBottom = async () => {
    // 等待 Vue 完成 DOM 更新
    await nextTick()
    
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  }
  
  /**
   * 清空消息列表
   * 
   * 【功能】重置消息列表，恢复到初始状态
   * 【调用时机】用户点击"清空消息"按钮
   */
  const clearMessages = () => {
    initMessages()
  }
  
  // ========================================================================
  // 对外暴露
  // ========================================================================
  
  return {
    // 状态
    messages,           // 消息列表
    userInput,          // 用户输入
    isTyping,           // AI 输入状态
    chatContainer,      // 容器 DOM 引用
    characterName,      // AI 角色名称
    initialMessage,     // 初始消息
    
    // 方法
    initMessages,       // 初始化消息
    addUserMessage,     // 添加用户消息
    addOrUpdateAIMessage, // 添加/更新 AI 消息
    scrollToBottom,     // 滚动到底部
    clearMessages       // 清空消息
  }
}
