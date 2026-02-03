<script setup>
/**
 * 消息气泡组件 (Message Bubble)
 * -------------------------------------------------------------------------
 * 负责渲染单条聊天消息，根据发送者角色自动适配样式。
 * 
 * 主要功能:
 * 1. 样式适配: 根据 role='ai' 或 'user' 切换布局方向和颜色。
 * 2. 格式化内容: 展示文本内容和时间戳。
 * 3. 头像展示: 展示对应的用户/机器人头像。
 */

import { computed } from 'vue'

// 定义 Props
const props = defineProps({
  message: {
    type: Object,
    required: true
  }
})

// 计算属性: 判断是否为 AI 发送的消息
const isAi = computed(() => props.message.role === 'ai')
</script>

<template>
  <!-- 
    外层容器
    - flex w-full: 占满宽度
    - justify-start / justify-end: 根据角色控制左对齐还是右对齐
  -->
  <div :class="['flex w-full', isAi ? 'justify-start' : 'justify-end']">
    
    <!-- 
      消息内容容器
      - max-w-[85%]: 限制消息最大宽度，防止铺满屏幕
      - flex-row / flex-row-reverse: 控制头像在左还是在右
    -->
    <div :class="['flex max-w-[85%] md:max-w-[70%]', isAi ? 'flex-row' : 'flex-row-reverse']">
      
      <!-- 
        头像区域 (Avatar)
        - flex-shrink-0: 防止头像被压缩
        - 根据角色显示不同的背景色和图标
      -->
      <div 
        class="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center mt-1 shadow-sm"
        :class="isAi ? 'bg-gradient-to-br from-blue-500 to-purple-600 ml-0 mr-3' : 'bg-gray-200 ml-3 mr-0 hidden'"
      >
        <i v-if="isAi" class="fas fa-robot text-white text-xs"></i>
        <i v-else class="fas fa-user text-gray-500 text-xs"></i>
      </div>

      <!-- 
        气泡主体 (Bubble)
        - rounded-2xl: 大圆角
        - rounded-tl-none / rounded-tr-none: 去掉指向头像那一角的圆角，形成气泡效果
        - AI 样式: 白底灰边，黑字
        - User 样式: 蓝色渐变底，白字
      -->
      <div 
        class="relative px-5 py-3.5 shadow-sm text-sm leading-relaxed"
        :class="[
          isAi 
            ? 'bg-white border border-gray-100 text-gray-800 rounded-2xl rounded-tl-none' 
            : 'bg-gradient-to-br from-blue-600 to-blue-700 text-white rounded-2xl rounded-tr-none'
        ]"
      >
        <!-- 消息正文: 保留换行符 -->
        <p class="whitespace-pre-wrap break-words">{{ message.content }}</p>
        
        <!-- 底部元数据: 时间戳与已读状态 -->
        <div 
          class="text-[10px] mt-1.5 flex items-center gap-1 opacity-70"
          :class="isAi ? 'justify-start text-gray-400' : 'justify-end text-blue-100'"
        >
          <span>{{ message.timestamp }}</span>
          <!-- 仅用户消息显示"双对勾"已读状态 -->
          <i v-if="!isAi" class="fas fa-check-double text-[10px]"></i>
        </div>
      </div>
    </div>
  </div>
</template>
