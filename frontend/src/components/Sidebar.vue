<script setup>
/**
 * 侧边栏组件 (Sidebar)
 * -------------------------------------------------------------------------
 * 展示历史对话记录和用户信息。
 * 
 * 主要功能:
 * 1. 历史记录列表: 展示最近的对话 Session。
 * 2. 搜索功能: 过滤历史对话 (UI 仅作展示，逻辑待实现)。
 * 3. 用户概览: 底部展示当前用户信息。
 * 4. 选中态样式: 高亮当前激活的会话。
 */

// 模拟历史数据
const history = [
  { id: 1, title: 'AI 界面设计研究', time: '10:30', active: true },
  { id: 2, title: 'Python 后端架构讨论', time: '昨天', active: false },
  { id: 3, title: 'Vue3 组件库选型', time: '前天', active: false },
  { id: 4, title: '多模态交互流程', time: '3天前', active: false },
  { id: 5, title: '色彩心理学分析', time: '上周', active: false },
]
</script>

<template>
  <!-- 侧边栏容器: flex-col 布局，顶部Header，中间List，底部Profile -->
  <div class="h-full bg-gray-50 border-r border-gray-200 flex flex-col">
    
    <!-- 顶部标题栏 -->
    <div class="h-16 px-5 flex items-center justify-between border-b border-gray-200 bg-white">
      <div class="flex items-center gap-2 text-gray-800 font-bold text-lg">
        <i class="fas fa-layer-group text-blue-600"></i>
        <span>Chat History</span>
      </div>
      <!-- 新建会话按钮 -->
      <button class="w-8 h-8 rounded-full hover:bg-gray-100 flex items-center justify-center text-gray-500 transition-colors">
        <i class="fas fa-plus"></i>
      </button>
    </div>

    <!-- 搜索框区域 -->
    <div class="p-4">
      <div class="relative">
        <i class="fas fa-search absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm"></i>
        <input 
          type="text" 
          placeholder="搜索对话..." 
          class="w-full bg-white border border-gray-200 rounded-xl pl-9 pr-3 py-2 text-sm focus:ring-2 focus:ring-blue-100 focus:border-blue-400 transition-all outline-none"
        >
      </div>
    </div>

    <!-- 历史记录列表 (可滚动) -->
    <div class="flex-1 overflow-y-auto px-3 py-2 space-y-1">
      <div class="px-3 py-2 text-xs font-semibold text-gray-400 uppercase tracking-wider">Recent</div>
      
      <!-- 列表项循环 -->
      <button 
        v-for="item in history" 
        :key="item.id"
        class="w-full text-left p-3 rounded-xl flex items-center gap-3 transition-all duration-200 group relative overflow-hidden"
        :class="item.active ? 'bg-white shadow-sm ring-1 ring-black/5' : 'hover:bg-gray-100/80'"
      >
        <!-- 选中态左侧高亮条 -->
        <div v-if="item.active" class="absolute left-0 top-0 w-1 h-full bg-blue-500 rounded-l-xl"></div>
        
        <!-- 图标容器 -->
        <div 
          class="w-8 h-8 rounded-full flex items-center justify-center shrink-0"
          :class="item.active ? 'bg-blue-100 text-blue-600' : 'bg-gray-200 text-gray-500 group-hover:bg-white group-hover:text-blue-500'"
        >
          <i class="fas fa-comment-alt text-xs"></i>
        </div>
        
        <!-- 文本信息 -->
        <div class="flex-1 min-w-0">
          <div class="font-medium text-sm truncate" :class="item.active ? 'text-gray-900' : 'text-gray-600'">
            {{ item.title }}
          </div>
          <div class="text-xs text-gray-400 mt-0.5">{{ item.time }}</div>
        </div>
      </button>
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
