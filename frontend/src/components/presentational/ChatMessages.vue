<script setup>
/**
 * 聊天消息列表组件 (Presentational Component)
 * =========================================================================
 * 
 * 【组件类型】Dumb Component（纯展示组件）
 * 【职责】
 * - 渲染消息列表
 * - 显示 AI 正在输入的动画提示
 * - 提供滚动容器
 * 
 * 【设计原则】
 * - 不包含业务逻辑，只负责展示
 * - 所有数据通过 props 接收
 * - 不处理消息发送，只显示消息
 * 
 * 【Props】
 * @prop {Array} messages - 消息列表数组
 * @prop {boolean} isTyping - AI 是否正在输入（显示输入提示）
 * 
 * 【Expose】
 * @expose {HTMLElement} container - 消息容器的 DOM 引用（用于滚动控制）
 * 
 * 【使用场景】
 * - 聊天界面的核心消息展示区域
 * - 父组件通过 ref 访问容器进行滚动操作
 */

import MessageBubble from './MessageBubble.vue'

// ========================================================================
// Props 定义
// ========================================================================

const props = defineProps({
  /** 
   * 消息列表
   * 每个消息对象包含：
   * - id: 唯一标识
   * - role: 'user' | 'ai'
   * - content: 消息内容
   * - timestamp: 时间戳
   * - type: 'text' | 'image' | 'audio'
   */
  messages: {
    type: Array,
    required: true
  },
  
  /** AI 是否正在输入（流式输出中） */
  isTyping: {
    type: Boolean,
    default: false
  }
})

// ========================================================================
// 对外暴露
// ========================================================================

/**
 * 暴露消息容器的 DOM 引用给父组件
 * 
 * 【用途】父组件可以通过 ref 访问容器实现：
 * - 自动滚动到最新消息
 * - 监听滚动事件
 * - 控制滚动位置
 */
defineExpose({
  container: null
})
</script>

<template>
  <div ref="container" class="flex-1 overflow-y-auto p-4 md:p-6 space-y-6 scroll-smooth">
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
</template>
