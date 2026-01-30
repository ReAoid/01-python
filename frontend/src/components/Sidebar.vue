<script setup>
import { ref, onMounted, computed } from 'vue'

/**
 * 侧边栏组件 (Sidebar)
 * -------------------------------------------------------------------------
 * 功能标签页系统，提供聊天、历史、配置、日志四个功能模块的切换入口。
 * 
 * 主要功能:
 * 1. 标签页切换: 支持聊天、历史、配置、日志四个功能标签。
 * 2. 状态通知: 通过 emit 通知父组件切换当前激活的标签页。
 * 3. 用户信息: 底部展示当前用户信息（从配置读取）。
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

// 用户配置
const userProfile = ref({
  name: 'Guest',
  nickname: 'User',
  age: null,
  gender: null,
  relationship_with_ai: null
})

// 切换标签页
const switchTab = (tabId) => {
  emit('tab-change', tabId)
}

// 加载用户配置
const loadUserProfile = async () => {
  try {
    const response = await fetch('/api/config/current')
    if (response.ok) {
      const data = await response.json()
      if (data.user_profile) {
        userProfile.value = data.user_profile
      }
      console.log('[Sidebar] Loaded user profile:', data.user_profile)
    }
  } catch (error) {
    console.error('[Sidebar] Failed to load user profile:', error)
  }
}

// 计算显示名称（优先使用昵称，否则使用姓名）
const displayName = computed(() => {
  return userProfile.value.nickname || userProfile.value.name || 'Guest User'
})

// 计算显示的用户信息（关系或年龄+性别）
const displayInfo = computed(() => {
  if (userProfile.value.relationship_with_ai) {
    return userProfile.value.relationship_with_ai
  }
  const parts = []
  if (userProfile.value.age) parts.push(`${userProfile.value.age}岁`)
  if (userProfile.value.gender) parts.push(userProfile.value.gender)
  return parts.length > 0 ? parts.join(' · ') : 'Free Plan'
})

// 生成头像 URL（基于名称）
const avatarUrl = computed(() => {
  const name = encodeURIComponent(displayName.value)
  return `https://ui-avatars.com/api/?name=${name}&background=0D8ABC&color=fff`
})

// 组件挂载时加载用户配置
onMounted(() => {
  loadUserProfile()
})
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
      <div class="w-full flex items-center gap-3 p-2 bg-gray-50 rounded-xl">
        <img :src="avatarUrl" class="w-9 h-9 rounded-full shadow-sm" :alt="displayName">
        <div class="flex-1 text-left min-w-0">
          <div class="text-sm font-semibold text-gray-900 truncate">{{ displayName }}</div>
          <div class="text-xs text-gray-500 truncate">{{ displayInfo }}</div>
        </div>
      </div>
    </div>
  </div>
</template>
