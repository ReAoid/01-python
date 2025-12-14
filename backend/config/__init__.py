# -*- coding: utf-8 -*-
"""配置常量定义"""

# 应用名称（会在用户文档下创建此目录）
APP_NAME = "AiAssistant"

# 需要管理的配置文件列表
CONFIG_FILES = [
    'core_config.json',      # 核心配置
]

# 默认配置数据（首次运行时使用）
DEFAULT_CONFIG_DATA = {
    'core_config.json': {
        'llm': {
            'default_model': 'gpt-3.5-turbo',
            'default_provider': 'openai',
            'temperature': 0.7,
            'max_tokens': None,
        },
        'api': {
            # API 密钥配置（也可以通过环境变量设置）
            'llm_api_key': None,  # 环境变量: LLM_API_KEY
            'llm_base_url': None,  # 环境变量: LLM_BASE_URL
            'llm_timeout': 60,     # 环境变量: LLM_TIMEOUT
            'serpapi_api_key': None,  # 环境变量: SERPAPI_API_KEY
        },
        'system': {
            'debug': False,
            'log_level': 'INFO',
        },
        'memory': {
            'max_history_length': 10,
            'embedding_model': 'Qwen/Qwen3-Embedding-8B',  # 环境变量: EMBEDDING_MODEL
        }
    }
}

