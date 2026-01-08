<script setup>
import { defineEmits } from 'vue'

/**
 * 侧边栏组件 (Sidebar)
 * -------------------------------------------------------------------------
 * 功能标签页系统，提供聊天、历史、配置、日志四个功能模块的切换入口。
 * 
 * 主要功能:
 * 1. 标签页切换: 支持聊天、历史、配置、日志四个功能标签。
 * 2. 状态通知: 通过 emit 通知父组件切换当前激活的标签页。
 * 3. 用户信息: 底部展示当前用户信息。
 */

// 接收父组件传递的当前激活标签
const props = defineProps({
  activeTab: {
    type: String,
    default: 'chat'
  }
})

// 定义事件发射器
const emit = defineEmits(['tab-change'])

// 标签页配置
const tabs = [
  { id: 'chat', label: '聊天', icon: 'fas fa-comments' },
  { id: 'history', label: '历史', icon: 'fas fa-history' },
  { id: 'settings', label: '配置', icon: 'fas fa-cog' },
  { id: 'logs', label: '日志', icon: 'fas fa-file-alt' }
]

// 切换标签页
const switchTab = (tabId) => {
  emit('tab-change', tabId)
}
</script>

<template>
  <!-- 侧边栏容器: flex-col 布局，顶部标签页，底部用户信息 -->
  <div class="h-full bg-gray-50 border-r border-gray-200 flex flex-col">
    
    <!-- 顶部标题栏 -->
    <div class="h-16 px-5 flex items-center justify-between border-b border-gray-200 bg-white">
      <div class="flex items-center gap-2 text-gray-800 font-bold text-lg">
        <i class="fas fa-layer-group text-blue-600"></i>
        <span>功能导航</span>
      </div>
    </div>

    <!-- 标签页区域 -->
    <div class="flex-1 overflow-y-auto p-3">
      <div class="space-y-1">
        <button 
          v-for="tab in tabs" 
          :key="tab.id"
          @click="switchTab(tab.id)"
          class="w-full text-left p-4 rounded-xl flex items-center gap-4 transition-all duration-200 group relative overflow-hidden"
          :class="activeTab === tab.id ? 'bg-white shadow-sm ring-1 ring-black/5' : 'hover:bg-gray-100/80'"
        >
          <!-- 选中态左侧高亮条 -->
          <div v-if="activeTab === tab.id" class="absolute left-0 top-0 w-1 h-full bg-blue-500 rounded-l-xl"></div>
          
          <!-- 图标容器 -->
          <div 
            class="w-10 h-10 rounded-full flex items-center justify-center shrink-0"
            :class="activeTab === tab.id ? 'bg-blue-100 text-blue-600' : 'bg-gray-200 text-gray-500 group-hover:bg-white group-hover:text-blue-500'"
          >
            <i :class="tab.icon" class="text-base"></i>
          </div>
          
          <!-- 文本信息 -->
          <div class="flex-1">
            <div class="font-medium text-base" :class="activeTab === tab.id ? 'text-gray-900' : 'text-gray-600'">
              {{ tab.label }}
            </div>
          </div>

          <!-- 箭头指示器 -->
          <div 
            v-if="activeTab === tab.id"
            class="text-blue-500"
          >
            <i class="fas fa-chevron-right text-sm"></i>
          </div>
        </button>
      </div>
    </div>

    <!-- 底部用户信息区域 -->
    <div class="p-4 border-t border-gray-200 bg-white">
      <button class="w-full flex items-center gap-3 p-2 hover:bg-gray-50 rounded-xl transition-colors">
        <img src="https://ui-avatars.com/api/?name=User&background=0D8ABC&color=fff" class="w-9 h-9 rounded-full shadow-sm" alt="User">
        <div class="flex-1 text-left">
          <div class="text-sm font-semibold text-gray-900">Guest User</div>
          <div class="text-xs text-gray-500">Free Plan</div>
        </div>
        <i class="fas fa-cog text-gray-400 hover:text-gray-600"></i>
      </button>
    </div>
  </div>
</template>
