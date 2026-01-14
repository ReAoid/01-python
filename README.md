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


    



