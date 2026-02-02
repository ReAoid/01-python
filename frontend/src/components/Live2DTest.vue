<template>
  <div class="live2d-test-page">
    <!-- 标题 -->
    <div class="header">
      <h1 class="title">
        <i class="fas fa-heart text-pink-500"></i>
        Live2D 模型测试
      </h1>
      <p class="subtitle">测试 Pio 模型的加载和交互功能</p>
    </div>

    <!-- 主要内容区 -->
    <div class="content-wrapper">
      <!-- Live2D 显示区 -->
      <div class="live2d-section">
        <div class="card">
          <h2 class="card-title">
            <i class="fas fa-user-circle mr-2"></i>
            Live2D 角色
          </h2>
          
          <div class="live2d-wrapper">
            <Live2DCharacter
              ref="live2dRef"
              :model-path="modelPath"
              :width="500"
              :height="500"
              :scale="0.5"
              :x="modelX"
              :y="modelY"
              :enable-drag="enableDrag"
              :state="currentState"
              :enable-mouse-tracking="enableMouseTracking"
              :enable-click="enableClick"
              :enable-lip-sync="enableLipSync"
              :audio-element="audioElement"
              :debug="true"
              @loaded="onModelLoaded"
              @error="onModelError"
            />
          </div>

          <!-- 状态指示 -->
          <div class="status-bar">
            <span class="status-badge" :class="statusClass">
              <i :class="statusIcon"></i>
              {{ statusText }}
            </span>
          </div>
        </div>
      </div>

      <!-- 控制面板 -->
      <div class="control-section">
        <!-- 基础信息 - 优化后的设计 -->
        <div class="card info-card">
          <div class="card-header">
            <h3 class="card-title">
              <i class="fas fa-info-circle"></i>
              模型信息
            </h3>
            <span class="status-indicator" :class="{ 'active': isLoaded }">
              <span class="status-dot"></span>
              {{ isLoaded ? '在线' : '离线' }}
            </span>
          </div>
          
          <div class="info-grid">
            <div class="info-row">
              <div class="info-icon">
                <i class="fas fa-cube"></i>
              </div>
              <div class="info-content">
                <div class="info-label">状态</div>
                <div class="info-value highlight">{{ currentState || 'idle' }}</div>
              </div>
            </div>
            
            <div class="info-row">
              <div class="info-icon">
                <i class="fas fa-check-circle"></i>
              </div>
              <div class="info-content">
                <div class="info-label">模型</div>
                <div class="info-value">{{ isLoaded ? '已加载' : '加载中...' }}</div>
              </div>
            </div>
            
            <div class="info-row">
              <div class="info-icon">
                <i class="fas fa-running"></i>
              </div>
              <div class="info-content">
                <div class="info-label">动作</div>
                <div class="info-value">{{ availableMotions.length > 0 ? availableMotions[0] : 'none' }}</div>
              </div>
            </div>
            
            <div class="info-row">
              <div class="info-icon">
                <i class="fas fa-film"></i>
              </div>
              <div class="info-content">
                <div class="info-label">可用动作</div>
                <div class="info-value">{{ availableMotions.length }} 个</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 状态控制 -->
        <div class="card">
          <h3 class="card-title">
            <i class="fas fa-sliders-h mr-2"></i>
            状态控制
          </h3>
          <div class="button-grid">
            <button 
              v-for="state in states" 
              :key="state.value"
              @click="changeState(state.value)"
              :class="['state-button', { active: currentState === state.value }]"
            >
              <i :class="state.icon"></i>
              {{ state.label }}
            </button>
          </div>
        </div>

        <!-- 动作播放 -->
        <div class="card">
          <h3 class="card-title">
            <i class="fas fa-play-circle mr-2"></i>
            动作播放
          </h3>
          <div class="motion-list">
            <button 
              v-for="motion in availableMotions" 
              :key="motion"
              @click="playMotion(motion)"
              class="motion-button"
            >
              <i class="fas fa-play mr-2"></i>
              {{ motion }}
            </button>
            <p v-if="availableMotions.length === 0" class="text-gray-500 text-sm">
              暂无可用动作
            </p>
          </div>
        </div>

        <!-- 交互设置 -->
        <div class="card">
          <h3 class="card-title">
            <i class="fas fa-cog mr-2"></i>
            交互设置
          </h3>
          <div class="settings-list">
            <label class="setting-item">
              <input type="checkbox" v-model="enableMouseTracking" />
              <span>鼠标跟踪（眼睛跟随光标）</span>
            </label>
            <label class="setting-item">
              <input type="checkbox" v-model="enableClick" />
              <span>点击交互</span>
            </label>
            <label class="setting-item">
              <input type="checkbox" v-model="enableLipSync" />
              <span>口型同步（需要音频）</span>
            </label>
            <label class="setting-item">
              <input type="checkbox" v-model="enableDrag" />
              <span>🖱️ 拖动模型（鼠标拖动改变位置）</span>
            </label>
          </div>
        </div>

        <!-- 位置控制 -->
        <div class="card">
          <h3 class="card-title">
            <i class="fas fa-arrows-alt mr-2"></i>
            位置控制
          </h3>
          <div class="position-controls">
            <div class="position-input-group">
              <label>
                <span class="position-label">X 坐标:</span>
                <input 
                  type="number" 
                  v-model.number="modelX" 
                  placeholder="默认: 居中"
                  class="position-input"
                  @change="updatePosition"
                />
              </label>
              <label>
                <span class="position-label">Y 坐标:</span>
                <input 
                  type="number" 
                  v-model.number="modelY" 
                  placeholder="默认: 底部80%"
                  class="position-input"
                  @change="updatePosition"
                />
              </label>
            </div>
            <div class="position-buttons">
              <button @click="resetPosition" class="position-button">
                <i class="fas fa-undo mr-2"></i>
                重置位置
              </button>
              <button @click="centerPosition" class="position-button">
                <i class="fas fa-compress-alt mr-2"></i>
                居中
              </button>
              <button @click="getModelPosition" class="position-button">
                <i class="fas fa-crosshairs mr-2"></i>
                获取当前位置
              </button>
            </div>
            <p class="text-sm text-gray-600 mt-2">
              💡 提示：启用"拖动模型"后，可以直接用鼠标拖动角色到任意位置
            </p>
          </div>
        </div>

        <!-- 音频测试 -->
        <div class="card">
          <h3 class="card-title">
            <i class="fas fa-volume-up mr-2"></i>
            音频测试（口型同步）
          </h3>
          <div class="audio-controls">
            <input 
              type="file" 
              ref="audioFileInput"
              accept="audio/*"
              @change="onAudioFileSelected"
              style="display: none;"
            />
            <button @click="selectAudioFile" class="audio-button">
              <i class="fas fa-folder-open mr-2"></i>
              选择音频文件
            </button>
            <button @click="playTestAudio" class="audio-button" :disabled="!hasAudioFile">
              <i class="fas fa-play mr-2"></i>
              播放测试音频
            </button>
            <button @click="stopTestAudio" class="audio-button secondary">
              <i class="fas fa-stop mr-2"></i>
              停止
            </button>
          </div>
          <p v-if="audioFileName" class="text-sm text-gray-600 mt-2">
            <i class="fas fa-file-audio mr-1"></i>
            {{ audioFileName }}
          </p>
          <p v-else class="text-sm text-gray-500 mt-2">
            💡 提示：选择一个音频文件来测试口型同步功能
          </p>
          <audio ref="audioRef" style="display: none;"></audio>
        </div>

        <!-- 说明 -->
        <div class="card">
          <h3 class="card-title">
            <i class="fas fa-question-circle mr-2"></i>
            使用说明
          </h3>
          <ul class="instruction-list">
            <li>✨ 移动鼠标，角色的眼睛会跟随光标</li>
            <li>👆 点击角色的不同部位会触发互动</li>
            <li>🎭 使用状态按钮切换角色状态</li>
            <li>🎬 点击动作按钮播放特定动作</li>
            <li>🎵 播放音频测试口型同步功能</li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import Live2DCharacter from './Live2DCharacter.vue'

// =========================================================================
// 状态定义
// =========================================================================

const live2dRef = ref(null)
const audioRef = ref(null)
const audioElement = ref(null)
const audioFileInput = ref(null)

const modelPath = ref('/live2d/Pio/model.json')
const currentState = ref('idle')
const isLoaded = ref(false)
const availableMotions = ref([])

const enableMouseTracking = ref(true)
const enableClick = ref(true)
const enableLipSync = ref(false)
const enableDrag = ref(false)

const hasAudioFile = ref(false)
const audioFileName = ref('')

// 模型位置控制
const modelX = ref(null) // null 表示使用默认值（居中）
const modelY = ref(null) // null 表示使用默认值（底部80%）

// 状态选项
const states = [
  { value: 'idle', label: '空闲', icon: 'fas fa-circle' },
  { value: 'thinking', label: '思考', icon: 'fas fa-brain' },
  { value: 'speaking', label: '说话', icon: 'fas fa-comment' },
  { value: 'interrupted', label: '打断', icon: 'fas fa-exclamation' }
]

// =========================================================================
// 计算属性
// =========================================================================

const statusClass = computed(() => {
  if (!isLoaded.value) return 'status-loading'
  return 'status-success'
})

const statusIcon = computed(() => {
  if (!isLoaded.value) return 'fas fa-spinner fa-spin'
  return 'fas fa-check-circle'
})

const statusText = computed(() => {
  if (!isLoaded.value) return '加载中...'
  return '运行正常'
})

// =========================================================================
// 生命周期
// =========================================================================

onMounted(() => {
  // 设置音频元素
  if (audioRef.value) {
    audioElement.value = audioRef.value
  }
})

// =========================================================================
// 方法
// =========================================================================

/**
 * 模型加载完成
 */
function onModelLoaded(data) {
  console.log('[Live2DTest] 模型加载完成:', data)
  isLoaded.value = true
  availableMotions.value = data.motions || []
}

/**
 * 模型加载错误
 */
function onModelError(error) {
  console.error('[Live2DTest] 模型加载错误:', error)
  isLoaded.value = false
}

/**
 * 切换状态
 */
function changeState(state) {
  console.log('[Live2DTest] 切换状态:', state)
  currentState.value = state
}

/**
 * 播放动作
 */
function playMotion(motion) {
  console.log('[Live2DTest] 播放动作:', motion)
  if (live2dRef.value) {
    live2dRef.value.playMotion(motion)
  }
}

/**
 * 选择音频文件
 */
function selectAudioFile() {
  if (audioFileInput.value) {
    audioFileInput.value.click()
  }
}

/**
 * 音频文件选择后
 */
function onAudioFileSelected(event) {
  const file = event.target.files[0]
  if (file && audioRef.value) {
    // 创建本地 URL
    const url = URL.createObjectURL(file)
    audioRef.value.src = url
    hasAudioFile.value = true
    audioFileName.value = file.name
    console.log('[Live2DTest] 音频文件已加载:', file.name)
  }
}

/**
 * 播放测试音频
 */
function playTestAudio() {
  if (audioRef.value && hasAudioFile.value) {
    enableLipSync.value = true
    audioRef.value.play()
    console.log('[Live2DTest] 播放测试音频')
  }
}

/**
 * 停止测试音频
 */
function stopTestAudio() {
  if (audioRef.value) {
    audioRef.value.pause()
    audioRef.value.currentTime = 0
    enableLipSync.value = false
    console.log('[Live2DTest] 停止测试音频')
  }
}

/**
 * 更新模型位置
 */
function updatePosition() {
  if (live2dRef.value && modelX.value !== null && modelY.value !== null) {
    live2dRef.value.setPosition(modelX.value, modelY.value)
    console.log('[Live2DTest] 更新位置:', { x: modelX.value, y: modelY.value })
  }
}

/**
 * 重置位置到默认值
 */
function resetPosition() {
  modelX.value = null
  modelY.value = null
  console.log('[Live2DTest] 重置位置到默认值')
  // 重新加载组件以应用默认位置
  location.reload()
}

/**
 * 居中模型
 */
function centerPosition() {
  modelX.value = 250 // 500 / 2
  modelY.value = 250 // 500 / 2
  updatePosition()
  console.log('[Live2DTest] 模型已居中')
}

/**
 * 获取模型当前位置
 */
function getModelPosition() {
  if (live2dRef.value) {
    const pos = live2dRef.value.getPosition()
    if (pos) {
      modelX.value = Math.round(pos.x)
      modelY.value = Math.round(pos.y)
      console.log('[Live2DTest] 当前位置:', pos)
      alert(`当前位置:\nX: ${pos.x.toFixed(2)}\nY: ${pos.y.toFixed(2)}`)
    }
  }
}

</script>

<style scoped>
.live2d-test-page {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 2rem;
}

.header {
  text-align: center;
  margin-bottom: 2rem;
}

.title {
  font-size: 2.5rem;
  font-weight: bold;
  color: white;
  margin-bottom: 0.5rem;
  text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
}

.subtitle {
  font-size: 1.125rem;
  color: rgba(255, 255, 255, 0.9);
}

.content-wrapper {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 2rem;
  max-width: 1400px;
  margin: 0 auto;
}

@media (max-width: 1024px) {
  .content-wrapper {
    grid-template-columns: 1fr;
  }
}

.card {
  background: white;
  border-radius: 1rem;
  padding: 1.5rem;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
  margin-bottom: 1.5rem;
}

.card-title {
  font-size: 1.25rem;
  font-weight: 600;
  color: #374151;
  margin-bottom: 1rem;
  display: flex;
  align-items: center;
}

.live2d-wrapper {
  display: flex;
  justify-content: center;
  align-items: flex-start;
  background: linear-gradient(135deg, #fdfcfb 0%, #e2d1c3 100%);
  border-radius: 0.75rem;
  padding: 0.5rem 1rem 1.5rem;
  min-height: 600px;
  overflow: hidden;
}

/* 调整 Live2D 模型位置 */
.live2d-wrapper :deep(canvas) {
  margin-top: -50px;
}

.status-bar {
  margin-top: 1rem;
  text-align: center;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  border-radius: 9999px;
  font-size: 0.875rem;
  font-weight: 500;
}

.status-loading {
  background: #fef3c7;
  color: #92400e;
}

.status-success {
  background: #d1fae5;
  color: #065f46;
}

/* 优化后的信息卡片样式 */
.info-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.info-card .card-title {
  color: white;
  font-size: 1.125rem;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  padding: 0.375rem 0.75rem;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 9999px;
  transition: all 0.3s;
}

.status-indicator.active {
  background: rgba(16, 185, 129, 0.3);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #fbbf24;
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

.status-indicator.active .status-dot {
  background: #10b981;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

.info-grid {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.info-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
  border-radius: 0.75rem;
  border: 1px solid rgba(255, 255, 255, 0.2);
  transition: all 0.3s;
}

.info-row:hover {
  background: rgba(255, 255, 255, 0.15);
  transform: translateX(5px);
}

.info-icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 0.5rem;
  font-size: 1.25rem;
}

.info-content {
  flex: 1;
}

.info-label {
  font-size: 0.75rem;
  opacity: 0.9;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.25rem;
}

.info-value {
  font-size: 1rem;
  font-weight: 600;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.info-value.highlight {
  font-size: 1.125rem;
  color: #fbbf24;
}

.info-item {
  display: flex;
  justify-content: space-between;
  padding: 0.5rem;
  background: #f9fafb;
  border-radius: 0.5rem;
}

.button-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.75rem;
}

.state-button {
  padding: 0.75rem 1rem;
  border: 2px solid #e5e7eb;
  background: white;
  border-radius: 0.5rem;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 0.875rem;
  font-weight: 500;
  color: #374151;
}

.state-button:hover {
  border-color: #8b5cf6;
  background: #f5f3ff;
}

.state-button.active {
  border-color: #8b5cf6;
  background: #8b5cf6;
  color: white;
}

.motion-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-height: 300px;
  overflow-y: auto;
}

.motion-button {
  padding: 0.5rem 1rem;
  background: #f3f4f6;
  border: 1px solid #e5e7eb;
  border-radius: 0.5rem;
  cursor: pointer;
  text-align: left;
  transition: all 0.2s;
  font-size: 0.875rem;
}

.motion-button:hover {
  background: #8b5cf6;
  color: white;
  border-color: #8b5cf6;
}

.settings-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.setting-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  cursor: pointer;
  padding: 0.5rem;
  border-radius: 0.5rem;
  transition: background 0.2s;
}

.setting-item:hover {
  background: #f9fafb;
}

.setting-item input[type="checkbox"] {
  width: 1.25rem;
  height: 1.25rem;
  cursor: pointer;
}

.audio-controls {
  display: flex;
  gap: 0.75rem;
}

.audio-button {
  flex: 1;
  padding: 0.75rem 1rem;
  background: #8b5cf6;
  color: white;
  border: none;
  border-radius: 0.5rem;
  cursor: pointer;
  font-size: 0.875rem;
  font-weight: 500;
  transition: background 0.2s;
}

.audio-button:hover {
  background: #7c3aed;
}

.audio-button.secondary {
  background: #6b7280;
}

.audio-button.secondary:hover {
  background: #4b5563;
}

.audio-button:disabled {
  background: #d1d5db;
  cursor: not-allowed;
  opacity: 0.6;
}

.audio-button:disabled:hover {
  background: #d1d5db;
}

.instruction-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.instruction-list li {
  padding: 0.5rem 0;
  color: #4b5563;
  font-size: 0.875rem;
  line-height: 1.5;
}

/* 位置控制样式 */
.position-controls {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.position-input-group {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.position-label {
  display: block;
  font-size: 0.875rem;
  font-weight: 500;
  color: #374151;
  margin-bottom: 0.5rem;
}

.position-input {
  width: 100%;
  padding: 0.5rem;
  border: 2px solid #e5e7eb;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  transition: border-color 0.2s;
}

.position-input:focus {
  outline: none;
  border-color: #8b5cf6;
}

.position-input::placeholder {
  color: #9ca3af;
}

.position-buttons {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.position-button {
  flex: 1;
  min-width: 120px;
  padding: 0.5rem 1rem;
  background: #f3f4f6;
  border: 1px solid #e5e7eb;
  border-radius: 0.5rem;
  cursor: pointer;
  font-size: 0.875rem;
  font-weight: 500;
  color: #374151;
  transition: all 0.2s;
}

.position-button:hover {
  background: #8b5cf6;
  color: white;
  border-color: #8b5cf6;
}

.position-button:active {
  transform: scale(0.98);
}
</style>
