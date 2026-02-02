/**
 * Live2D 控制器类
 * -------------------------------------------------------------------------
 * 封装 Live2D 模型的加载、动画控制、交互等功能
 * 
 * 功能：
 * 1. 模型加载和初始化
 * 2. 动画播放控制
 * 3. 鼠标交互（跟随、点击）
 * 4. 口型同步
 * 5. 表情切换
 * 
 * 重要说明：
 * - 使用 pixi-live2d-display/cubism2 来支持 Cubism 2.1 模型（.moc 格式）
 * - Pio 模型是 Cubism 2.1 格式，需要 live2d.min.js 运行时
 */

import * as PIXI from 'pixi.js'
// 关键修复：使用 Cubism 2.1 专用包，而不是主包（主包默认只支持 Cubism 4）
import { Live2DModel } from 'pixi-live2d-display/cubism2'

console.log('[Live2D Init] 开始初始化 Live2D 控制器')
console.log('[Live2D Init] 使用 pixi-live2d-display/cubism2 包')

// 将 PIXI 暴露到 window 上,这样插件可以通过 window.PIXI.Ticker 自动更新模型
window.PIXI = PIXI
console.log('[Live2D Init] ✅ PIXI 已暴露到全局:', typeof window.PIXI)

// 详细检查 Live2D Cubism 2.1 运行时
console.log('[Live2D Init] 检查运行时环境...')
console.log('[Live2D Init] - window.Live2D:', typeof window.Live2D)
console.log('[Live2D Init] - window.Live2DModelWebGL:', typeof window.Live2DModelWebGL)

if (window.Live2D) {
  console.log('[Live2D Init] ✅ Cubism 2.1 运行时已检测到')
  console.log('[Live2D Init] Live2D 版本:', window.Live2D.getVersionStr())
  console.log('[Live2D Init] Live2D 对象属性:', Object.keys(window.Live2D))
  
  // 将 Live2D.ModelWebGL 暴露为全局（某些情况下需要）
  if (window.Live2D.ModelWebGL) {
    window.Live2DModelWebGL = window.Live2D.ModelWebGL
    console.log('[Live2D Init] ✅ Live2DModelWebGL 已注册到全局')
  } else {
    console.warn('[Live2D Init] ⚠️ Live2D.ModelWebGL 不存在')
  }
  
  // 注册 PIXI Ticker
  try {
    Live2DModel.registerTicker(PIXI.Ticker)
    console.log('[Live2D Init] ✅ Live2DModel 已注册 PIXI Ticker')
  } catch (error) {
    console.error('[Live2D Init] ❌ 注册 PIXI Ticker 失败:', error)
  }
  
  console.log('[Live2D Init] ✅ 初始化完成，准备加载模型')
} else {
  console.error('[Live2D Init] ❌ Cubism 2.1 运行时未找到')
  console.error('[Live2D Init] 请确保在 HTML 中加载了 live2d.min.js:')
  console.error('[Live2D Init]   <script src="/lib/live2d.min.js"></script>')
  console.error('[Live2D Init] 当前 window 对象上的相关属性:')
  console.error('[Live2D Init]   - Live2D:', typeof window.Live2D)
  console.error('[Live2D Init]   - Live2DModelWebGL:', typeof window.Live2DModelWebGL)
}

export class Live2DController {
  constructor(options = {}) {
    this.app = null
    this.model = null
    this.container = null
    this.isLoaded = false
    this.currentMotion = null
    this.isDestroyed = false
    
    // 配置选项
    this.options = {
      modelPath: options.modelPath || '/live2d/Pio/model.json',
      width: options.width || 300,
      height: options.height || 400,
      scale: options.scale || 0.3,
      x: options.x || (options.width || 300) / 2,  // 默认居中
      y: options.y || (options.height || 400) * 0.8,  // 默认在底部80%位置
      enableMouseTracking: options.enableMouseTracking !== false,
      enableClick: options.enableClick !== false,
      ...options
    }
    
    // 口型同步相关
    this.audioContext = null
    this.audioAnalyser = null
    this.lipSyncValue = 0
    this.lipSyncEnabled = false
  }

  /**
   * 初始化 PIXI 应用
   */
  async init(canvasElement) {
    if (this.isDestroyed) {
      console.warn('[Live2D] Controller已被销毁，无法初始化')
      return false
    }

    try {
      console.log('[Live2D] 准备初始化 PIXI，目标尺寸:', {
        width: this.options.width,
        height: this.options.height
      })
      
      // 手动设置 canvas 尺寸 (修复 PIXI v8 的尺寸问题)
      canvasElement.width = this.options.width
      canvasElement.height = this.options.height
      console.log('[Live2D] Canvas 尺寸已设置 (创建 PIXI 前):', {
        width: canvasElement.width,
        height: canvasElement.height
      })
      
      // 创建 PIXI 应用
      this.app = new PIXI.Application({
        view: canvasElement,
        width: this.options.width,
        height: this.options.height,
        transparent: true,
        backgroundAlpha: 0,
        antialias: true,
        resolution: window.devicePixelRatio || 1,
        autoDensity: true
      })

      console.log('[Live2D] PIXI应用初始化成功')
      console.log('[Live2D] Canvas尺寸 (创建 PIXI 后):', {
        width: canvasElement.width,
        height: canvasElement.height,
        style: {
          width: canvasElement.style.width,
          height: canvasElement.style.height
        }
      })
      
      // 如果 PIXI 覆盖了尺寸，再次强制设置
      if (canvasElement.width !== this.options.width || canvasElement.height !== this.options.height) {
        console.warn('[Live2D] PIXI 覆盖了 canvas 尺寸，强制重新设置')
        canvasElement.width = this.options.width
        canvasElement.height = this.options.height
        // 调整 renderer 尺寸
        this.app.renderer.resize(this.options.width, this.options.height)
        console.log('[Live2D] Canvas尺寸已强制修正:', {
          width: canvasElement.width,
          height: canvasElement.height
        })
      }
      
      console.log('[Live2D] PIXI Stage:', {
        width: this.app.stage.width,
        height: this.app.stage.height,
        children: this.app.stage.children.length
      })
      return true
    } catch (error) {
      console.error('[Live2D] PIXI应用初始化失败:', error)
      return false
    }
  }

  /**
   * 加载 Live2D 模型
   */
  async loadModel() {
    if (!this.app) {
      console.error('[Live2D] PIXI应用未初始化')
      return false
    }

    if (this.isDestroyed) {
      console.warn('[Live2D] Controller已被销毁，无法加载模型')
      return false
    }

    try {
      console.log('[Live2D] 开始加载模型:', this.options.modelPath)
      
      // 加载模型
      // 注意：在 PixiJS v7 中，autoInteract 可能导致兼容性问题，暂时禁用
      this.model = await Live2DModel.from(this.options.modelPath, {
        autoInteract: false,  // 禁用自动交互以避免 PixiJS v7 兼容性问题
        autoUpdate: true
      })

      if (this.isDestroyed) {
        console.warn('[Live2D] 加载过程中Controller被销毁')
        return false
      }

      // 设置模型属性
      this.model.anchor.set(0.5, 0.5)
      this.model.scale.set(this.options.scale)
      this.model.position.set(this.options.x, this.options.y)

      console.log('[Live2D] 模型配置:', {
        canvasSize: { width: this.options.width, height: this.options.height },
        scale: this.options.scale,
        position: { x: this.options.x, y: this.options.y },
        anchor: { x: 0.5, y: 0.5 },
        modelOriginalSize: { 
          width: this.model.width, 
          height: this.model.height 
        },
        modelScaledSize: {
          width: this.model.width * this.options.scale,
          height: this.model.height * this.options.scale
        }
      })

      // 添加到舞台
      this.app.stage.addChild(this.model)
      console.log('[Live2D] 模型已添加到舞台, stage children:', this.app.stage.children.length)
      
      // 获取模型的边界框
      const bounds = this.model.getBounds()
      console.log('[Live2D] 模型边界框:', {
        x: bounds.x,
        y: bounds.y,
        width: bounds.width,
        height: bounds.height,
        right: bounds.x + bounds.width,
        bottom: bounds.y + bounds.height
      })
      
      // 检查模型是否在可视区域内
      const isVisible = bounds.x < this.options.width && 
                       bounds.y < this.options.height &&
                       bounds.x + bounds.width > 0 &&
                       bounds.y + bounds.height > 0
      console.log('[Live2D] 模型是否在可视区域:', isVisible)
      
      if (!isVisible) {
        console.warn('[Live2D] ⚠️ 模型不在可视区域内！可能需要调整位置或缩放')
      }

      // 启用鼠标跟踪
      if (this.options.enableMouseTracking) {
        this.enableMouseTracking()
      }

      // 启用拖动功能
      if (this.options.enableDrag) {
        this.enableDrag()
      }

      // 播放默认待机动画
      this.playMotion('idle')

      this.isLoaded = true
      console.log('[Live2D] 模型加载成功')
      
      return true
    } catch (error) {
      console.error('[Live2D] 模型加载失败:', error)
      return false
    }
  }

  /**
   * 播放动作
   * @param {string} group - 动作组名称 (idle, tap_body等)
   * @param {number} index - 动作索引（可选）
   */
  playMotion(group = 'idle', index = 0) {
    if (!this.model || !this.isLoaded) {
      console.warn('[Live2D] 模型未加载，无法播放动作')
      return false
    }

    try {
      // 检查是否有该动作组
      const motions = this.model.internalModel?.motionManager?.definitions
      if (!motions || !motions[group]) {
        console.warn(`[Live2D] 未找到动作组: ${group}`)
        return false
      }

      // 播放动作
      this.model.motion(group, index)
      this.currentMotion = group
      console.log(`[Live2D] 播放动作: ${group}[${index}]`)
      
      return true
    } catch (error) {
      console.error('[Live2D] 播放动作失败:', error)
      return false
    }
  }

  /**
   * 启用鼠标跟踪（眼睛跟随光标）
   */
  enableMouseTracking() {
    if (!this.model || !this.app) return

    const stage = this.app.stage
    
    // PixiJS v7+ 使用 eventMode 代替 interactive
    stage.eventMode = 'static'
    
    // 在 PIXI v7+ 中，screen 在 renderer 上
    // 使用 canvas 尺寸创建 hitArea
    stage.hitArea = new PIXI.Rectangle(0, 0, this.options.width, this.options.height)
    
    stage.on('pointermove', (event) => {
      if (!this.model || this.isDestroyed) return
      
      const point = event.global
      
      // 将屏幕坐标转换为模型坐标系
      // Live2D 的 Y 轴是从下到上的,需要反转
      const modelX = (point.x - this.model.x) / this.model.width
      const modelY = -(point.y - this.model.y) / this.model.height  // 注意这里加了负号
      
      // 更新模型的注视点
      if (this.model.internalModel?.focusController) {
        this.model.internalModel.focusController.focus(modelX, modelY)
      }
    })

    console.log('[Live2D] 鼠标跟踪已启用')
  }

  /**
   * 启用拖动功能
   */
  enableDrag() {
    if (!this.model || !this.app) return

    this.model.eventMode = 'static'
    this.model.cursor = 'move'
    
    let dragData = null
    
    // 开始拖动
    this.model.on('pointerdown', (event) => {
      if (!this.model || this.isDestroyed) return
      
      dragData = {
        startX: this.model.x,
        startY: this.model.y,
        pointerX: event.global.x,
        pointerY: event.global.y
      }
      
      this.model.alpha = 0.8
      console.log('[Live2D] 开始拖动模型')
    })
    
    // 拖动中
    this.app.stage.on('pointermove', (event) => {
      if (!dragData || !this.model || this.isDestroyed) return
      
      const dx = event.global.x - dragData.pointerX
      const dy = event.global.y - dragData.pointerY
      
      this.model.x = dragData.startX + dx
      this.model.y = dragData.startY + dy
    })
    
    // 结束拖动
    this.app.stage.on('pointerup', () => {
      if (dragData && this.model) {
        this.model.alpha = 1
        console.log('[Live2D] 拖动结束，新位置:', {
          x: this.model.x,
          y: this.model.y
        })
      }
      dragData = null
    })
    
    this.app.stage.on('pointerupoutside', () => {
      if (dragData && this.model) {
        this.model.alpha = 1
      }
      dragData = null
    })

    console.log('[Live2D] 拖动功能已启用')
  }

  /**
   * 启用口型同步
   * @param {HTMLAudioElement} audioElement - 音频元素
   */
  async enableLipSync(audioElement) {
    if (!this.model || !this.isLoaded) {
      console.warn('[Live2D] 模型未加载，无法启用口型同步')
      return false
    }

    try {
      // 创建音频上下文
      if (!this.audioContext) {
        this.audioContext = new (window.AudioContext || window.webkitAudioContext)()
      }

      // 创建分析器
      this.audioAnalyser = this.audioContext.createAnalyser()
      this.audioAnalyser.fftSize = 256
      
      // 连接音频源
      const source = this.audioContext.createMediaElementSource(audioElement)
      source.connect(this.audioAnalyser)
      this.audioAnalyser.connect(this.audioContext.destination)

      this.lipSyncEnabled = true
      this.startLipSyncLoop()

      console.log('[Live2D] 口型同步已启用')
      return true
    } catch (error) {
      console.error('[Live2D] 启用口型同步失败:', error)
      return false
    }
  }

  /**
   * 口型同步循环
   */
  startLipSyncLoop() {
    if (!this.lipSyncEnabled || this.isDestroyed) return

    const dataArray = new Uint8Array(this.audioAnalyser.frequencyBinCount)
    
    const update = () => {
      if (!this.lipSyncEnabled || this.isDestroyed) return

      // 获取音频频率数据
      this.audioAnalyser.getByteFrequencyData(dataArray)
      
      // 计算平均音量
      let sum = 0
      for (let i = 0; i < dataArray.length; i++) {
        sum += dataArray[i]
      }
      const average = sum / dataArray.length
      
      // 归一化到 0-1 范围，并添加平滑
      const targetValue = Math.min(average / 50, 1.0)
      this.lipSyncValue += (targetValue - this.lipSyncValue) * 0.3
      
      // 更新模型嘴部参数
      this.setMouthOpen(this.lipSyncValue)
      
      requestAnimationFrame(update)
    }
    
    update()
  }

  /**
   * 停用口型同步
   */
  disableLipSync() {
    this.lipSyncEnabled = false
    this.lipSyncValue = 0
    this.setMouthOpen(0)
    console.log('[Live2D] 口型同步已停用')
  }

  /**
   * 设置嘴部开合度
   * @param {number} value - 开合度 (0-1)
   */
  setMouthOpen(value) {
    if (!this.model || !this.isLoaded) return

    try {
      // Live2D Cubism 2.x 使用 PARAM_MOUTH_OPEN_Y
      const coreModel = this.model.internalModel?.coreModel
      if (coreModel && coreModel.setParamFloat) {
        coreModel.setParamFloat('PARAM_MOUTH_OPEN_Y', value)
      }
    } catch (error) {
      // 静默失败，避免频繁报错
    }
  }

  /**
   * 设置模型状态（根据AI状态）
   * @param {string} state - 状态 (idle, thinking, speaking, interrupted)
   */
  setState(state) {
    console.log(`[Live2D] 设置状态: ${state}`)
    
    switch (state) {
      case 'idle':
        this.playMotion('idle')
        this.disableLipSync()
        break
      case 'thinking':
        // 可以播放思考动作，如果有的话
        this.playMotion('idle')
        break
      case 'speaking':
        // 播放说话动作（如果有）
        this.playMotion('idle')
        break
      case 'interrupted':
        // 播放惊讶表情
        this.playMotion('idle')
        break
      default:
        this.playMotion('idle')
    }
  }

  /**
   * 调整模型大小
   */
  resize(width, height) {
    if (!this.app) return

    this.app.renderer.resize(width, height)
    
    // 重新定位模型到中心
    if (this.model) {
      this.model.position.set(width / 2, height * 0.85)
    }
  }

  /**
   * 销毁控制器
   */
  destroy() {
    console.log('[Live2D] 开始销毁控制器')
    
    this.isDestroyed = true
    this.isLoaded = false
    
    // 停用口型同步
    this.disableLipSync()
    
    // 关闭音频上下文
    if (this.audioContext) {
      this.audioContext.close()
      this.audioContext = null
    }
    
    // 销毁模型
    if (this.model) {
      this.model.destroy()
      this.model = null
    }
    
    // 销毁 PIXI 应用
    if (this.app) {
      this.app.destroy(true, { children: true, texture: true, baseTexture: true })
      this.app = null
    }
    
    console.log('[Live2D] 控制器已销毁')
  }

  /**
   * 获取可用的动作列表
   */
  getAvailableMotions() {
    if (!this.model || !this.isLoaded) return []

    try {
      const motions = this.model.internalModel?.motionManager?.definitions
      return motions ? Object.keys(motions) : []
    } catch (error) {
      console.error('[Live2D] 获取动作列表失败:', error)
      return []
    }
  }
}

export default Live2DController
