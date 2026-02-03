<script setup>
/**
 * 系统通知管理器 (Smart/Container Component)
 * -------------------------------------------------------------------------
 * 负责管理所有系统通知的业务逻辑和状态
 * 
 * 【设计原则】
 * - 处理所有业务逻辑（定时器、状态管理、生命周期）
 * - 协调多个展示组件
 * - 不直接渲染复杂 UI，委托给 Presentational 组件
 * 
 * 【职责】
 * - 管理通知队列
 * - 控制通知的显示和隐藏
 * - 处理定时器逻辑
 * - 管理进度条更新
 * - 生成唯一 ID
 * 
 * 【使用方式】
 * ```vue
 * <SystemNotificationManager ref="notificationRef" />
 * 
 * // 在父组件中调用
 * notificationRef.value.addNotification('消息内容', 5000)
 * ```
 */

import { reactive, onUnmounted } from 'vue'
import NotificationToast from '../presentational/NotificationToast.vue'

// ========================================================================
// 状态管理
// ========================================================================

/** 通知队列 */
const notifications = reactive([])

/** 通知 ID 计数器 */
let notificationId = 0

/** 存储所有定时器引用，用于清理 */
const allTimers = new Set()

// ========================================================================
// 核心方法
// ========================================================================

/**
 * 添加新通知
 * 
 * @param {string} message - 通知消息内容
 * @param {number} duration - 显示时长（毫秒），默认 5000ms (5秒)
 * 
 * 【流程】
 * 1. 创建通知对象
 * 2. 添加到队列
 * 3. 启动显示动画
 * 4. 启动进度条倒计时
 * 5. 设置自动关闭定时器
 */
const addNotification = (message, duration = 5000) => {
  const id = notificationId++
  
  // 创建通知对象
  const notification = reactive({
    id,
    message,
    duration,
    isVisible: false,
    isFading: false,
    progress: 100,
    timers: {
      show: null,
      hide: null,
      progress: null
    }
  })

  // 添加到队列
  notifications.push(notification)
  
  // 延迟显示（触发进入动画）
  const showTimer = setTimeout(() => {
    notification.isVisible = true
  }, 50)
  notification.timers.show = showTimer
  allTimers.add(showTimer)

  // 进度条倒计时更新
  const startTime = Date.now()
  const progressTimer = setInterval(() => {
    const elapsed = Date.now() - startTime
    notification.progress = Math.max(0, 100 - (elapsed / duration * 100))
  }, 100) // 每 100ms 更新一次
  notification.timers.progress = progressTimer
  allTimers.add(progressTimer)

  // 自动关闭定时器
  const hideTimer = setTimeout(() => {
    closeNotification(id)
  }, duration)
  notification.timers.hide = hideTimer
  allTimers.add(hideTimer)

  console.log('[Notification] Added:', { id, message, duration })
}

/**
 * 关闭指定通知
 * 
 * @param {number} id - 通知 ID
 * 
 * 【流程】
 * 1. 查找通知对象
 * 2. 清除所有定时器
 * 3. 开始淡出动画
 * 4. 等待动画完成后从队列移除
 */
const closeNotification = (id) => {
  const notification = notifications.find(n => n.id === id)
  if (!notification) return

  console.log('[Notification] Closing:', id)

  // 清除该通知的所有定时器
  Object.values(notification.timers).forEach(timer => {
    if (timer) {
      clearTimeout(timer)
      clearInterval(timer)
      allTimers.delete(timer)
    }
  })

  // 开始淡出动画
  notification.isFading = true

  // 等待动画完成后移除（500ms 与 CSS transition 时间一致）
  const removeTimer = setTimeout(() => {
    const index = notifications.findIndex(n => n.id === id)
    if (index > -1) {
      notifications.splice(index, 1)
      console.log('[Notification] Removed:', id)
    }
  }, 500)
  allTimers.add(removeTimer)
}

// ========================================================================
// 生命周期
// ========================================================================

/**
 * 组件卸载时清理
 * 
 * 【清理工作】
 * - 清除所有定时器，防止内存泄漏
 * - 清空通知队列
 */
onUnmounted(() => {
  console.log('[Notification] Cleaning up timers...')
  
  // 清除所有定时器
  allTimers.forEach(timer => {
    clearTimeout(timer)
    clearInterval(timer)
  })
  allTimers.clear()
  
  // 清空队列
  notifications.splice(0, notifications.length)
})

// ========================================================================
// 暴露给父组件的方法
// ========================================================================

defineExpose({
  addNotification,
  closeNotification,
  // 暴露队列，方便调试
  notifications
})
</script>

<template>
  <!-- 
    通知容器
    - fixed: 固定定位在屏幕右上角
    - pointer-events-none: 不阻挡底层元素的鼠标事件
  -->
  <div class="fixed top-20 right-6 z-50 pointer-events-none">
    <!-- 
      通知列表
      - pointer-events-auto: 恢复通知本身的鼠标事件
      - flex flex-col gap-3: 垂直排列，间距 12px
    -->
    <div class="flex flex-col gap-3 pointer-events-auto">
      <!-- 
        TransitionGroup 实现列表动画
        - name="notification": 使用自定义动画
        - tag="div": 渲染为 div 元素
      -->
      <TransitionGroup
        name="notification"
        tag="div"
        class="flex flex-col gap-3"
      >
        <!-- 
          循环渲染每个通知
          - 使用 NotificationToast (Dumb 组件) 负责 UI
          - 通过 props 传递所有状态
          - 通过 @close 事件接收用户交互
        -->
        <NotificationToast
          v-for="notification in notifications"
          :key="notification.id"
          :message="notification.message"
          :is-visible="notification.isVisible"
          :is-fading="notification.isFading"
          :progress="notification.progress"
          @close="closeNotification(notification.id)"
        />
      </TransitionGroup>
    </div>
  </div>
</template>

<style scoped>
/* ========================================================================
   TransitionGroup 动画定义
   ======================================================================== */

/* 进入动画 */
.notification-enter-active {
  transition: all 0.5s ease-out;
}

.notification-enter-from {
  opacity: 0;
  transform: translateX(50px);
}

.notification-enter-to {
  opacity: 1;
  transform: translateX(0);
}

/* 离开动画 */
.notification-leave-active {
  transition: all 0.5s ease-in;
}

.notification-leave-from {
  opacity: 1;
  transform: translateX(0);
}

.notification-leave-to {
  opacity: 0;
  transform: translateX(50px);
}

/* 移动动画（当有通知被移除时，其他通知平滑移动） */
.notification-move {
  transition: transform 0.5s ease;
}
</style>
