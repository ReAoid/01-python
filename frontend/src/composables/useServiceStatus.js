/**
 * 服务状态检查 Composable
 * =========================================================================
 * 
 * 【功能】
 * - 检查 TTS 和 ASR 服务的运行状态
 * - 提供统一的服务状态查询接口
 * - 处理服务状态错误
 * 
 * 【API 端点】
 * - GET /api/tts/status - 检查 TTS 服务状态
 * - GET /api/asr/status - 检查 ASR 服务状态
 * 
 * 【返回格式】
 * {
 *   status: "ok" | "error",
 *   message: string,
 *   enabled: boolean
 * }
 */

import { ref } from 'vue'

export function useServiceStatus() {
  /** TTS 服务状态 */
  const ttsStatus = ref({
    enabled: false,
    available: false,
    message: ''
  })

  /** ASR 服务状态 */
  const asrStatus = ref({
    enabled: false,
    available: false,
    message: ''
  })

  /**
   * 检查 TTS 服务状态
   * 
   * @returns {Promise<Object>} 服务状态对象
   * @throws {Error} 网络错误或服务不可用
   */
  const checkTTSStatus = async () => {
    try {
      const response = await fetch('/api/tts/status', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json'
        }
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const data = await response.json()
      
      ttsStatus.value = {
        enabled: data.enabled || false,
        available: data.status === 'ok',
        message: data.message || ''
      }

      console.log('[Service] TTS status checked:', ttsStatus.value)
      return ttsStatus.value
    } catch (error) {
      console.error('[Service] Failed to check TTS status:', error)
      ttsStatus.value = {
        enabled: false,
        available: false,
        message: error.message || '无法连接到 TTS 服务'
      }
      throw error
    }
  }

  /**
   * 检查 ASR 服务状态
   * 
   * @returns {Promise<Object>} 服务状态对象
   * @throws {Error} 网络错误或服务不可用
   */
  const checkASRStatus = async () => {
    try {
      const response = await fetch('/api/asr/status', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json'
        }
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const data = await response.json()
      
      asrStatus.value = {
        enabled: data.enabled || false,
        available: data.status === 'ok',
        message: data.message || ''
      }

      console.log('[Service] ASR status checked:', asrStatus.value)
      return asrStatus.value
    } catch (error) {
      console.error('[Service] Failed to check ASR status:', error)
      asrStatus.value = {
        enabled: false,
        available: false,
        message: error.message || '无法连接到 ASR 服务'
      }
      throw error
    }
  }

  /**
   * 检查所有服务状态
   * 
   * @returns {Promise<Object>} 包含所有服务状态的对象
   */
  const checkAllServices = async () => {
    const results = await Promise.allSettled([
      checkTTSStatus(),
      checkASRStatus()
    ])

    return {
      tts: results[0].status === 'fulfilled' ? results[0].value : ttsStatus.value,
      asr: results[1].status === 'fulfilled' ? results[1].value : asrStatus.value
    }
  }

  return {
    ttsStatus,
    asrStatus,
    checkTTSStatus,
    checkASRStatus,
    checkAllServices
  }
}
