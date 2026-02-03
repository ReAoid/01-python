<script setup>
/**
 * 通知气泡组件 (Dumb/Presentational Component)
 * -------------------------------------------------------------------------
 * 纯展示组件，负责渲染单个通知气泡的 UI
 * 
 * 【设计原则】
 * - 只负责展示，不包含业务逻辑
 * - 所有数据通过 props 接收
 * - 所有交互通过 emit 传递给父组件
 * - 不管理自己的生命周期和状态
 * 
 * 【职责】
 * - 渲染通知消息内容
 * - 显示进度条
 * - 处理关闭按钮点击
 * - 显示动画效果（由父组件控制）
 */

// 定义 Props
const props = defineProps({
  /** 通知消息内容 */
  message: {
    type: String,
    required: true
  },
  /** 是否可见（控制显示动画） */
  isVisible: {
    type: Boolean,
    default: true
  },
  /** 是否正在淡出（控制消失动画） */
  isFading: {
    type: Boolean,
    default: false
  },
  /** 进度百分比 (0-100) */
  progress: {
    type: Number,
    default: 100,
    validator: (value) => value >= 0 && value <= 100
  }
})

// 定义 Emits
const emit = defineEmits(['close'])

/**
 * 处理关闭按钮点击
 * 纯粹地将事件传递给父组件，不做任何处理
 */
const handleClose = () => {
  emit('close')
}
</script>

<template>
  <!-- 
    浮动通知容器
    - transition-all: 平滑过渡动画
    - 动画状态完全由父组件通过 props 控制
  -->
  <div 
    class="transition-all duration-500 ease-in-out transform"
    :class="{
      'opacity-100 translate-x-0': isVisible && !isFading,
      'opacity-0 translate-x-12': !isVisible || isFading
    }"
  >
    <!-- 
      通知卡片
      - min-w-[320px] max-w-[400px]: 限制宽度范围
      - shadow-2xl: 大阴影增强立体感
      - backdrop-blur-sm: 背景模糊效果
    -->
    <div 
      class="min-w-[320px] max-w-[400px] bg-gradient-to-br from-blue-50 to-indigo-50 
             border border-blue-200 rounded-xl shadow-2xl backdrop-blur-sm"
    >
      <!-- 内容区域 -->
      <div class="flex items-start gap-3 p-4">
        <!-- 图标 -->
        <div class="flex-shrink-0 w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 
                    flex items-center justify-center shadow-md">
          <i class="fas fa-info-circle text-white text-lg"></i>
        </div>

        <!-- 文字内容 -->
        <div class="flex-1 min-w-0">
          <h4 class="text-sm font-semibold text-gray-800 mb-1">系统提示</h4>
          <p class="text-sm text-gray-600 leading-relaxed break-words whitespace-pre-wrap">
            {{ message }}
          </p>
        </div>

        <!-- 关闭按钮 -->
        <button 
          @click="handleClose"
          class="flex-shrink-0 w-6 h-6 rounded-full hover:bg-gray-200 
                 flex items-center justify-center transition-colors duration-200"
          aria-label="关闭通知"
        >
          <i class="fas fa-times text-gray-400 text-xs"></i>
        </button>
      </div>

      <!-- 进度条 -->
      <div class="h-1 bg-gray-100 rounded-b-xl overflow-hidden">
        <div 
          class="h-full bg-gradient-to-r from-blue-500 to-indigo-600 transition-all duration-100 ease-linear"
          :style="{ width: `${progress}%` }"
        ></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 无需自定义样式，所有样式都在 template 中使用 Tailwind CSS */
</style>
