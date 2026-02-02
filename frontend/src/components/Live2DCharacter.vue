<template>
  <div 
    class="live2d-container" 
    ref="containerRef"
    :style="{ width: `${width}px`, height: `${height}px` }"
  >
    <!-- Canvas 容器 -->
    <canvas ref="canvasRef" class="live2d-canvas"></canvas>
    
    <!-- 加载状态 -->
    <div v-if="loading" class="loading-overlay">
      <div class="loading-spinner">
        <i class="fas fa-spinner fa-spin text-4xl text-purple-500"></i>
        <p class="mt-4 text-gray-600">加载 Live2D 模型中...</p>
      </div>
    </div>
    
    <!-- 错误提示 -->
    <div v-if="error" class="error-overlay">
      <div class="error-message">
        <i class="fas fa-exclamation-triangle text-4xl text-red-500"></i>
        <p class="mt-4 text-gray-700">{{ error }}</p>
        <button @click="retry" class="retry-button">
          <i class="fas fa-redo mr-2"></i>重试
        </button>
      </div>
    </div>
    
    <!-- 调试信息 (开发模式) -->
    <div v-if="debug && controller" class="debug-info">
      <div class="text-xs text-gray-600">
        <p>状态: {{ state }}</p>
        <p>模型: {{ isLoaded ? '已加载' : '未加载' }}</p>
        <p>动作: {{ currentMotion || 'none' }}</p>
        <p>可用动作: {{ availableMotions.length }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { Live2DController } from '../utils/Live2DController.js'

// =========================================================================
// Props 定义
// =========================================================================

const props = defineProps({
  // 模型路径
  modelPath: {
    type: String,
    default: '/live2d/Pio/model.json'
  },
  // Canvas 宽度
  width: {
    type: Number,
    default: 300
  },
  // Canvas 高度
  height: {
    type: Number,
    default: 400
  },
  // 模型缩放
  scale: {
    type: Number,
    default: 0.3
  },
  // 模型 X 位置（默认居中）
  x: {
    type: Number,
    default: null
  },
  // 模型 Y 位置（默认在底部80%）
  y: {
    type: Number,
    default: null
  },
  // 是否启用拖动
  enableDrag: {
    type: Boolean,
    default: false
  },
  // AI 状态 (idle, thinking, speaking, interrupted)
  state: {
    type: String,
    default: 'idle'
  },
  // 是否启用鼠标跟踪
  enableMouseTracking: {
    type: Boolean,
    default: true
  },
  // 是否启用点击交互
  enableClick: {
    type: Boolean,
    default: true
  },
  // 音频元素（用于口型同步）
  audioElement: {
    type: HTMLAudioElement,
    default: null
  },
  // 是否启用口型同步
  enableLipSync: {
    type: Boolean,
    default: false
  },
  // 调试模式
  debug: {
    type: Boolean,
    default: false
  }
})

// =========================================================================
// Emits 定义
// =========================================================================

const emit = defineEmits(['loaded', 'error', 'motion-start', 'motion-end'])

// =========================================================================
// 状态定义
// =========================================================================

const containerRef = ref(null)
const canvasRef = ref(null)
const controller = ref(null)
const loading = ref(true)
const error = ref(null)
const isLoaded = ref(false)
const currentMotion = ref(null)
const availableMotions = ref([])

// =========================================================================
// 生命周期
// =========================================================================

onMounted(async () => {
  console.log('[Live2DCharacter] 组件挂载')
  await initLive2D()
})

onUnmounted(() => {
  console.log('[Live2DCharacter] 组件卸载')
  destroyLive2D()
})

// =========================================================================
// 监听器
// =========================================================================

// 监听状态变化
watch(() => props.state, (newState) => {
  if (controller.value && isLoaded.value) {
    console.log('[Live2DCharacter] 状态变化:', newState)
    controller.value.setState(newState)
  }
})

// 监听口型同步
watch(() => props.enableLipSync, (enabled) => {
  if (!controller.value || !isLoaded.value) return
  
  if (enabled && props.audioElement) {
    controller.value.enableLipSync(props.audioElement)
  } else {
    controller.value.disableLipSync()
  }
})

// 监听音频元素变化
watch(() => props.audioElement, (newAudio) => {
  if (!controller.value || !isLoaded.value || !props.enableLipSync) return
  
  if (newAudio) {
    controller.value.enableLipSync(newAudio)
  }
})

// =========================================================================
// 方法
// =========================================================================

/**
 * 初始化 Live2D
 */
async function initLive2D() {
  try {
    loading.value = true
    error.value = null
    
    // 等待 DOM 渲染
    await nextTick()
    
    if (!canvasRef.value) {
      throw new Error('Canvas 元素未找到')
    }
    
    // 创建控制器
    controller.value = new Live2DController({
      modelPath: props.modelPath,
      width: props.width,
      height: props.height,
      scale: props.scale,
      x: props.x !== null ? props.x : props.width / 2,
      y: props.y !== null ? props.y : props.height * 0.85,
      enableMouseTracking: props.enableMouseTracking,
      enableClick: props.enableClick,
      enableDrag: props.enableDrag
    })
    
    // 初始化 PIXI
    const initSuccess = await controller.value.init(canvasRef.value)
    if (!initSuccess) {
      throw new Error('PIXI 初始化失败')
    }
    
    // 加载模型
    const loadSuccess = await controller.value.loadModel()
    if (!loadSuccess) {
      throw new Error('模型加载失败')
    }
    
    // 加载成功
    isLoaded.value = true
    loading.value = false
    
    // 获取可用动作
    availableMotions.value = controller.value.getAvailableMotions()
    console.log('[Live2DCharacter] 可用动作:', availableMotions.value)
    
    // 触发加载完成事件
    emit('loaded', {
      motions: availableMotions.value
    })
    
    // 如果需要启用口型同步
    if (props.enableLipSync && props.audioElement) {
      controller.value.enableLipSync(props.audioElement)
    }
    
  } catch (err) {
    console.error('[Live2DCharacter] 初始化失败:', err)
    error.value = err.message || '加载失败'
    loading.value = false
    emit('error', err)
  }
}

/**
 * 销毁 Live2D
 */
function destroyLive2D() {
  if (controller.value) {
    controller.value.destroy()
    controller.value = null
  }
  isLoaded.value = false
}

/**
 * 重试加载
 */
async function retry() {
  destroyLive2D()
  await initLive2D()
}

/**
 * 播放动作
 */
function playMotion(group, index = 0) {
  if (controller.value && isLoaded.value) {
    const success = controller.value.playMotion(group, index)
    if (success) {
      currentMotion.value = group
      emit('motion-start', { group, index })
    }
    return success
  }
  return false
}

/**
 * 设置状态
 */
function setState(state) {
  if (controller.value && isLoaded.value) {
    controller.value.setState(state)
  }
}

/**
 * 设置模型位置
 */
function setPosition(x, y) {
  if (controller.value && isLoaded.value && controller.value.model) {
    controller.value.model.x = x
    controller.value.model.y = y
  }
}

/**
 * 获取模型位置
 */
function getPosition() {
  if (controller.value && isLoaded.value && controller.value.model) {
    return {
      x: controller.value.model.x,
      y: controller.value.model.y
    }
  }
  return null
}

// 暴露方法给父组件
defineExpose({
  playMotion,
  setState,
  setPosition,
  getPosition,
  controller,
  isLoaded,
  availableMotions
})

</script>

<style scoped>
.live2d-container {
  position: relative;
  display: inline-block;
  overflow: hidden;
}

.live2d-canvas {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
}

/* 加载动画 */
.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
}

.loading-spinner {
  text-align: center;
}

/* 错误提示 */
.error-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.95);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
}

.error-message {
  text-align: center;
  padding: 2rem;
}

.retry-button {
  margin-top: 1rem;
  padding: 0.5rem 1.5rem;
  background: #8b5cf6;
  color: white;
  border: none;
  border-radius: 0.5rem;
  cursor: pointer;
  font-size: 0.875rem;
  transition: background 0.2s;
}

.retry-button:hover {
  background: #7c3aed;
}

/* 调试信息 */
.debug-info {
  position: absolute;
  top: 0.5rem;
  left: 0.5rem;
  background: rgba(0, 0, 0, 0.7);
  color: white;
  padding: 0.5rem;
  border-radius: 0.25rem;
  font-family: monospace;
  z-index: 20;
}
</style>
