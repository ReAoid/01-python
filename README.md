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
1.部署模型
```text
直接执行backend/utils/genie_client.py文件自动下载
or
将https://huggingface.co/High-Logic/Genie/tree/main/GenieData下的文件放到backend/config/tts/GenieData下
```
2.部署参考音频
```text
直接执行backend/utils/genie_client.py文件自动下载
or
将https://huggingface.co/High-Logic/Genie/tree/main/CharacterModels下的文件放到backend/config/tts/GenieData/CharacterModels下
```
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


    



