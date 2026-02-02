<script setup>
/**
 * 配置编辑器组件
 * -------------------------------------------------------------------------
 * 提供可编辑的配置表单，支持 LLM、TTS、ASR 等配置的修改
 */

import { ref, computed, watch, onMounted } from 'vue'

// Props
const props = defineProps({
  config: {
    type: Object,
    required: true
  },
  isEditing: {
    type: Boolean,
    default: false
  },
  editingConfig: {
    type: Object,
    default: null
  }
})

// Emits
const emit = defineEmits(['update', 'test-tts', 'test-asr'])

// 当前显示的配置（编辑时显示编辑中的，否则显示原始的）
const displayConfig = computed(() => {
  const config = props.isEditing && props.editingConfig ? props.editingConfig : props.config
  
  // 确保 live2d 配置存在
  if (config && !config.live2d) {
    config.live2d = {
      enabled: false,
      position: {
        x: 100,
        y: 500,
        max_x: 1920,
        max_y: 1080
      }
    }
  }
  
  return config
})
</script>

<template>
  <div class="space-y-6">
    <!-- LLM 配置 -->
    <div class="bg-white rounded-lg border border-gray-200 shadow-sm">
      <div class="px-6 py-4 border-b border-gray-200 bg-gray-50">
        <h4 class="font-semibold text-gray-900 flex items-center gap-2">
          <i class="fas fa-brain text-pink-500"></i>
          大语言模型配置 (LLM)
        </h4>
      </div>
      <div class="p-6 space-y-4">
        <!-- 对话模型 -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">对话模型</label>
            <input 
              v-model="displayConfig.chat_llm.model"
              :disabled="!props.isEditing"
              type="text"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
              placeholder="例如: gpt-4, claude-3-opus"
            />
          </div>
          
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">服务提供商</label>
            <input 
              v-model="displayConfig.chat_llm.provider"
              :disabled="!props.isEditing"
              type="text"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
              placeholder="例如: openai, anthropic"
            />
          </div>
          
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">温度 (Temperature)</label>
            <input 
              v-model.number="displayConfig.chat_llm.temperature"
              :disabled="!props.isEditing"
              type="number"
              min="0"
              max="2"
              step="0.1"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
            />
            <p class="text-xs text-gray-500 mt-1">范围: 0.0 - 2.0，值越高越随机</p>
          </div>
          
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">最大 Token 数</label>
            <input 
              v-model.number="displayConfig.chat_llm.max_tokens"
              :disabled="!props.isEditing"
              type="number"
              min="1"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
              placeholder="留空表示不限制"
            />
          </div>
        </div>
        
        <!-- API 配置 -->
        <div class="pt-4 border-t border-gray-200">
          <h5 class="text-sm font-semibold text-gray-700 mb-3">API 配置</h5>
          <div class="grid grid-cols-1 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">API 地址</label>
              <input 
                v-model="displayConfig.chat_llm.api.base_url"
                :disabled="!props.isEditing"
                type="text"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
                placeholder="例如: https://api.openai.com/v1"
              />
            </div>
            
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">API Key</label>
              <input 
                v-model="displayConfig.chat_llm.api.key"
                :disabled="!props.isEditing"
                type="password"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed font-mono text-sm"
                placeholder="sk-..."
              />
            </div>
            
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">超时时间（秒）</label>
              <input 
                v-model.number="displayConfig.chat_llm.api.timeout"
                :disabled="!props.isEditing"
                type="number"
                min="1"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
              />
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 嵌入模型配置 -->
    <div class="bg-white rounded-lg border border-gray-200 shadow-sm">
      <div class="px-6 py-4 border-b border-gray-200 bg-gray-50">
        <h4 class="font-semibold text-gray-900 flex items-center gap-2">
          <i class="fas fa-project-diagram text-purple-500"></i>
          嵌入模型配置 (Embedding)
        </h4>
      </div>
      <div class="p-6 space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">嵌入模型</label>
          <input 
            v-model="displayConfig.embedding_llm.model"
            :disabled="!props.isEditing"
            type="text"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
            placeholder="例如: text-embedding-ada-002"
          />
        </div>
        
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">API 地址</label>
          <input 
            v-model="displayConfig.embedding_llm.api.base_url"
            :disabled="!props.isEditing"
            type="text"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
            placeholder="例如: https://api.openai.com/v1"
          />
        </div>
        
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">API Key</label>
          <input 
            v-model="displayConfig.embedding_llm.api.key"
            :disabled="!props.isEditing"
            type="password"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed font-mono text-sm"
            placeholder="sk-..."
          />
        </div>
      </div>
    </div>

    <!-- TTS 配置 -->
    <div class="bg-white rounded-lg border border-gray-200 shadow-sm">
      <div class="px-6 py-4 border-b border-gray-200 bg-gray-50">
        <h4 class="font-semibold text-gray-900 flex items-center gap-2">
          <i class="fas fa-volume-up text-green-500"></i>
          文本转语音配置 (TTS)
        </h4>
      </div>
      <div class="p-6 space-y-4">
        <div class="flex items-center justify-between">
          <div>
            <label class="block text-sm font-medium text-gray-700">启用 TTS</label>
            <p class="text-xs text-gray-500 mt-1">开启后可使用语音回复功能</p>
          </div>
          <label class="relative inline-flex items-center cursor-pointer">
            <input 
              v-model="displayConfig.tts.enabled"
              :disabled="!props.isEditing"
              type="checkbox"
              class="sr-only peer"
            />
            <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
          </label>
        </div>
        
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">引擎</label>
            <input 
              v-model="displayConfig.tts.engine"
              :disabled="!props.isEditing"
              type="text"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
            />
          </div>
          
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">角色</label>
            <input 
              v-model="displayConfig.tts.active_character"
              :disabled="!props.isEditing"
              type="text"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
            />
          </div>
          
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">语言</label>
            <select 
              v-model="displayConfig.tts.language"
              :disabled="!props.isEditing"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
            >
              <option value="zh">中文</option>
              <option value="en">英文</option>
              <option value="jp">日文</option>
            </select>
          </div>
        </div>
        
        <!-- 服务器配置 -->
        <div class="pt-4 border-t border-gray-200">
          <h5 class="text-sm font-semibold text-gray-700 mb-3">服务器配置</h5>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">主机地址</label>
              <input 
                v-model="displayConfig.tts.server.host"
                :disabled="!props.isEditing"
                type="text"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
              />
            </div>
            
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">端口</label>
              <input 
                v-model.number="displayConfig.tts.server.port"
                :disabled="!props.isEditing"
                type="number"
                min="1"
                max="65535"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
              />
            </div>
            
            <div class="flex items-end">
              <label class="flex items-center gap-2 cursor-pointer">
                <input 
                  v-model="displayConfig.tts.server.auto_start"
                  :disabled="!props.isEditing"
                  type="checkbox"
                  class="rounded text-blue-500"
                />
                <span class="text-sm text-gray-700">自动启动</span>
              </label>
            </div>
          </div>
        </div>
        
        <!-- TTS 测试按钮 -->
        <div class="pt-4 border-t border-gray-200">
          <button 
            @click="emit('test-tts')"
            class="px-4 py-2 bg-green-500 text-white rounded-lg text-sm hover:bg-green-600 transition-colors flex items-center gap-2"
          >
            <i class="fas fa-play"></i>
            测试 TTS
          </button>
        </div>
      </div>
    </div>

    <!-- ASR 配置 -->
    <div class="bg-white rounded-lg border border-gray-200 shadow-sm">
      <div class="px-6 py-4 border-b border-gray-200 bg-gray-50">
        <h4 class="font-semibold text-gray-900 flex items-center gap-2">
          <i class="fas fa-microphone text-red-500"></i>
          语音识别配置 (ASR)
        </h4>
      </div>
      <div class="p-6 space-y-4">
        <div class="flex items-center justify-between">
          <div>
            <label class="block text-sm font-medium text-gray-700">启用 ASR</label>
            <p class="text-xs text-gray-500 mt-1">开启后可使用语音输入功能</p>
          </div>
          <label class="relative inline-flex items-center cursor-pointer">
            <input 
              v-model="displayConfig.asr.enabled"
              :disabled="!props.isEditing"
              type="checkbox"
              class="sr-only peer"
            />
            <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
          </label>
        </div>
        
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">引擎</label>
            <input 
              v-model="displayConfig.asr.engine"
              :disabled="!props.isEditing"
              type="text"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
            />
          </div>
          
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">模型</label>
            <input 
              v-model="displayConfig.asr.model"
              :disabled="!props.isEditing"
              type="text"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
            />
          </div>
          
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">语言</label>
            <select 
              v-model="displayConfig.asr.language"
              :disabled="!props.isEditing"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
            >
              <option value="zh">中文</option>
              <option value="en">英文</option>
              <option value="jp">日文</option>
            </select>
          </div>
        </div>
        
        <!-- 音频配置 -->
        <div class="pt-4 border-t border-gray-200">
          <h5 class="text-sm font-semibold text-gray-700 mb-3">音频配置</h5>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">采样率 (Hz)</label>
              <input 
                v-model.number="displayConfig.asr.audio.sample_rate"
                :disabled="!props.isEditing"
                type="number"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
              />
            </div>
            
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">声道数</label>
              <input 
                v-model.number="displayConfig.asr.audio.channels"
                :disabled="!props.isEditing"
                type="number"
                min="1"
                max="2"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
              />
            </div>
            
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-2">采样位深</label>
              <input 
                v-model.number="displayConfig.asr.audio.sample_width"
                :disabled="!props.isEditing"
                type="number"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
              />
            </div>
          </div>
        </div>
        
        <!-- ASR 测试按钮 -->
        <div class="pt-4 border-t border-gray-200">
          <button 
            @click="emit('test-asr')"
            class="px-4 py-2 bg-red-500 text-white rounded-lg text-sm hover:bg-red-600 transition-colors flex items-center gap-2"
          >
            <i class="fas fa-microphone"></i>
            测试 ASR
          </button>
        </div>
      </div>
    </div>

    <!-- Live2D 配置 -->
    <div class="bg-white rounded-lg border border-gray-200 shadow-sm">
      <div class="px-6 py-4 border-b border-gray-200 bg-gray-50">
        <h4 class="font-semibold text-gray-900 flex items-center gap-2">
          <i class="fas fa-heart text-pink-500"></i>
          Live2D 模型配置
        </h4>
      </div>
      <div class="p-6 space-y-4">
        <div class="flex items-center justify-between">
          <div>
            <label class="block text-sm font-medium text-gray-700">显示 Live2D 模型</label>
            <p class="text-xs text-gray-500 mt-1">开启后在聊天界面显示 Live2D 角色</p>
          </div>
          <label class="relative inline-flex items-center cursor-pointer">
            <input 
              v-model="displayConfig.live2d.enabled"
              :disabled="!props.isEditing"
              type="checkbox"
              class="sr-only peer"
            />
            <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-pink-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-pink-600"></div>
          </label>
        </div>
        
        <!-- 位置控制 -->
        <div class="pt-4 border-t border-gray-200">
          <h5 class="text-sm font-semibold text-gray-700 mb-4">模型位置</h5>
          
          <!-- X 轴位置 -->
          <div class="mb-6">
            <div class="flex items-center justify-between mb-2">
              <label class="text-sm font-medium text-gray-700">X 轴位置（水平）</label>
              <span class="text-sm font-mono text-gray-600 bg-gray-100 px-2 py-1 rounded">
                {{ displayConfig.live2d.position.x }}px
              </span>
            </div>
            <input 
              v-model.number="displayConfig.live2d.position.x"
              :disabled="!props.isEditing"
              type="range"
              min="0"
              :max="displayConfig.live2d.position.max_x || 1920"
              step="10"
              class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
              :class="props.isEditing ? 'accent-pink-600' : ''"
            />
            <div class="flex justify-between text-xs text-gray-500 mt-1">
              <span>0</span>
              <span>{{ displayConfig.live2d.position.max_x || 1920 }}</span>
            </div>
          </div>
          
          <!-- Y 轴位置 -->
          <div class="mb-4">
            <div class="flex items-center justify-between mb-2">
              <label class="text-sm font-medium text-gray-700">Y 轴位置（垂直）</label>
              <span class="text-sm font-mono text-gray-600 bg-gray-100 px-2 py-1 rounded">
                {{ displayConfig.live2d.position.y }}px
              </span>
            </div>
            <input 
              v-model.number="displayConfig.live2d.position.y"
              :disabled="!props.isEditing"
              type="range"
              min="0"
              :max="displayConfig.live2d.position.max_y || 1080"
              step="10"
              class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
              :class="props.isEditing ? 'accent-pink-600' : ''"
            />
            <div class="flex justify-between text-xs text-gray-500 mt-1">
              <span>0</span>
              <span>{{ displayConfig.live2d.position.max_y || 1080 }}</span>
            </div>
          </div>
          
          <!-- 位置提示 -->
          <div class="mt-4 p-3 bg-pink-50 rounded-lg">
            <div class="flex items-start gap-2">
              <i class="fas fa-info-circle text-pink-500 mt-0.5"></i>
              <div class="text-xs text-pink-700">
                <p class="font-medium mb-1">位置说明：</p>
                <ul class="list-disc list-inside space-y-0.5">
                  <li>X 轴：0 表示最左侧，最大值表示最右侧</li>
                  <li>Y 轴：0 表示最顶部，最大值表示最底部</li>
                  <li>最大值会根据窗口大小自动调整</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
