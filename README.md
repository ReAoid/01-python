# 01-python

## 克隆仓库
```shell
git clone https://github.com/ReAoid/01-python.git
```

## 安装依赖
```shell
conda create -n 01-python python=3.12
conda activate 01-python
cd backend

pip install -r requirements.txt
# PyTorch使用cpu
pip install -r backend/requirements.txt -r backend/requirements-torch-cpu.txt
# PyTorch使用gpu
pip install -r backend/requirements.txt -r backend/requirements-torch-gpu.txt
```

## 系统环境变量
需要配置 `core_config.json` 文件到`backend/config/core_config.json`，结构为：
```json
{
    "_comment": "核心配置文件 - 应用程序的主配置",
    "chat_llm": {
        "_comment": "聊天大语言模型配置",
        "model": "替换为聊天模型",
        "provider": "openai",
        "temperature": 0.7,
        "max_tokens": null,
        "api": {
            "key": "替换为LLM API Key",
            "base_url": "替换为LLM API 服务地址",
            "timeout": 60
        }
    },
    "embedding_llm": {
        "_comment": "向量嵌入模型配置",
        "model": "Qwen/Qwen3-Embedding-8B",
        "api": {
            "key": "替换为Embedding API Key",
            "base_url": "替换为Embedding API 服务地址",
            "timeout": 60
        }
    },
    "system": {
        "debug": true,
        "log_level": "INFO"
    },
    "memory": {
        "max_history_length": 100,
        "min_summaries_for_structuring": 3,
        "structuring_batch_size": 5,
        "retrieval_top_k": 5,
        "retrieval_threshold": 0.6
    },
    "tts": {
        "enabled": true,
        "engine": "genie",
        "genie_data_dir": "backend/data/tts",
        "server": {
            "host": "127.0.0.1",
            "port": 8001,
            "auto_start": false
        },
        "active_character": "feibi",
        "language": "zh"
    },
    "third_party_api": {
        "_comment": "第三方服务API配置",
        "serpapi_api_key": "替换为SerpApi Key（可选）"
    }
}
```

## 前端部署
```shell
cd frontend
npm install
```

> 📖 **详细说明**: 查看 [frontend/README.md](frontend/README.md) 了解前端项目的依赖配置和技术栈说明。

### 常见问题排查
如果运行 `npm run dev` 时遇到以下错误：
```
ERROR: Could not resolve "@pixi/core"
ERROR: Could not resolve "@pixi/display"
```

**解决方案**：这是因为 `pixi-live2d-display` 需要 PixiJS 的模块化包。执行以下命令安装缺失的依赖：
```bash
npm install @pixi/core @pixi/display @pixi/math @pixi/sprite @pixi/ticker
```

## Live2D部署

> 📚 **官方文档**: [pixi-live2d-display 中文文档](https://github.com/guansss/pixi-live2d-display/blob/master/README.zh.md)

### 1. 安装依赖
Live2D 依赖已包含在 `package.json` 中，执行 `npm install` 时会自动安装：
- `pixi.js@7` - 2D渲染引擎（完整版）
- `@pixi/core`, `@pixi/display`, `@pixi/math`, `@pixi/sprite`, `@pixi/ticker` - PixiJS 模块化包（必需）
- `pixi-live2d-display@0.5.0-beta` - Live2D 模型加载和显示库

**⚠️ 重要提示**: `pixi-live2d-display@0.5.0-beta` 需要 PixiJS 的模块化包才能正常工作。如果遇到 `Could not resolve "@pixi/core"` 等错误，请确保安装了所有 `@pixi/*` 依赖包：
```bash
npm install @pixi/core @pixi/display @pixi/math @pixi/sprite @pixi/ticker
```

### 2. 下载运行时库（Cubism Core）
Live2D Cubism 2.1 运行时库已自动下载到 `frontend/public/lib/live2d.min.js`

**版本说明**：
- **Cubism 2.1** 模型（`.moc` 格式）→ 需要 `live2d.min.js`
- **Cubism 3/4** 模型（`.moc3` 格式）→ 需要 `live2dcubismcore.min.js`

当前 Pio 模型使用 Cubism 2.1，所以只需要 `live2d.min.js`

**CDN 链接**（可选）：
- Cubism 2.1: https://cdn.jsdelivr.net/gh/dylanNew/live2d/webgl/Live2D/lib/live2d.min.js
- Cubism 4: https://cubism.live2d.com/sdk-web/cubismcore/live2dcubismcore.min.js

### 3. 准备模型文件
将 Live2D 模型文件放置到 `frontend/public/live2d/` 目录下，例如：
```
frontend/public/live2d/
└── Pio/
    ├── model.json          # 模型配置文件
    ├── model.moc           # 模型数据文件 (Cubism 2.1)
    ├── textures/           # 贴图文件夹
    │   └── *.png
    └── motions/            # 动作文件夹
        └── *.mtn
```

### 4. 使用方法
在 Vue 组件中引入 Live2D 组件：
```vue
<template>
  <Live2DCharacter 
    model-path="/live2d/Pio/model.json"
    :width="300"
    :height="400"
  />
</template>

<script setup>
import Live2DCharacter from './components/Live2DCharacter.vue'
</script>
```

### 5. 测试 Live2D
访问测试页面验证模型加载：
```
http://localhost:5173/test-live2d.html
```

### 6. Live2D 配置管理
在系统配置页面可以管理 Live2D 模型的显示和位置：

**配置选项**：
- **显示 Live2D 模型**: 开关按钮，控制是否在聊天界面显示模型
- **X 轴位置**: 滑动条控制水平位置（0-1920px）
- **Y 轴位置**: 滑动条控制垂直位置（0-1080px）

**使用步骤**：
1. 进入配置页面（点击侧边栏的"配置"标签）
2. 点击"编辑配置"按钮
3. 滚动到页面最下方找到"Live2D 模型配置"
4. 开启"显示 Live2D 模型"开关
5. 使用滑动条调整模型位置
6. 点击"保存"按钮保存配置

## TTS部署

### 方式一：一键自动安装（推荐）

使用 `all_ready.py` 脚本自动检测和安装所有模型：

```shell
# 1. 检测系统状态（不执行下载）
python all_ready.py --check-only

# 2. 自动安装所有缺失的模型
python all_ready.py

# 3. 仅安装TTS模型
python all_ready.py --tts-only
```

脚本会自动：
- 检测依赖包是否安装
- 下载 Genie-TTS 基础模型（GenieData）
- 下载默认角色模型（feibi）
- 验证模型文件完整性



### 方式二：手动安装

1. **部署基础模型**
```text
直接执行backend/genie_server.py文件自动下载
or
将https://huggingface.co/High-Logic/Genie/tree/main/GenieData下的文件放到backend/data/tts/GenieData下
```

2. **部署角色模型**
```text
直接执行backend/genie_server.py文件自动下载
or
将https://huggingface.co/High-Logic/Genie/tree/main/CharacterModels下的文件放到backend/data/tts/GenieData/CharacterModels下
```

## ASR部署（可选）

如果需要语音识别功能：

```shell
# 1. 检测ASR模型状态
python all_ready.py --asr-only --check-only

# 2. 根据提示手动下载FunASR模型

```

**快速配置**：
1. 启用ASR：修改 `backend/config/core_config.json` 中的 `asr.enabled` 为 `true`
2. 配置引擎：设置 `asr.engine` 为 `funasr_nano`
3. 下载模型：按照 `backend/data/asr/README_FUNASR_SETUP.md` 的说明下载
4. 配置路径：设置 `asr.model_path` 为模型文件路径
## 启动顺序
1.启动TTS服务（如果启用了TTS）
```shell
cd backend
python genie_server.py
```
2.启动后端服务
```shell
cd backend
python main.py
```
3.启动前端服务    
```shell
cd frontend
npm run dev
```


    



