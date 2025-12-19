<script setup>
/**
 * 根组件 (Root Component)
 * -------------------------------------------------------------------------
 * 应用的顶级容器，负责定义全屏布局结构。
 * 
 * 结构说明:
 * - 这是一个全屏容器 (h-screen)，背景色为浅灰 (bg-gray-50)。
 * - 它居中显示核心聊天界面 (ChatInterface)。
 * - 在移动端 (p-0) 铺满全屏，在桌面端 (md:p-4) 保留四周间距。
 */
import ChatInterface from './components/ChatInterface.vue'
</script>

<template>
  <!-- 
    主容器:
    - h-screen: 占据整个视口高度
    - flex items-center justify-center: 内容居中显示
  -->
  <div class="h-screen w-full bg-gray-50 flex items-center justify-center p-0 md:p-4 font-sans text-gray-900">
    <!-- 加载核心聊天界面组件 -->
    <ChatInterface />
  </div>
</template>
