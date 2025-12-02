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
        'system': {
            'debug': False,
            'log_level': 'INFO',
        },
        'memory': {
            'max_history_length': 10,
        }
    }
}

