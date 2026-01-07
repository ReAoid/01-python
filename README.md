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
    "llm": {
        "default_model": "替换模型",
        "default_provider": "openai",
        "temperature": 0.7
    },
    "api": {
        "llm_api_key": "替换key",
        "llm_base_url": "替换请求地址",
        "llm_timeout": 60,
        "serpapi_api_key": "替换key"
    },
    "system": {
        "debug": true,
        "log_level": "INFO"
    },
    "memory": {
        "max_history_length": 100,
        "embedding_model": "替换使用模型"
    },
    "tts": {
        "enabled": true,
        "engine": "genie",
        "genie_data_dir": "backend/config/tts",
        "server": {
            "host": "127.0.0.1",
            "port": 8001,
            "auto_start": false
        },
        "active_character": "feibi",
        "language": "zh"
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


    



