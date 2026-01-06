import os
import shutil
import platform
import json
from pathlib import Path
from typing import Dict, List, Any

# 常量定义
APP_NAME = "灵依"
CONFIG_FILES = ['core_config.json', 'characters.json', 'voice_storage.json']

# 默认配置数据
DEFAULT_CONFIG_DATA = {
    'core_config.json': {
        'llm': {
            'default_model': 'gpt-3.5-turbo',
            'default_provider': 'openai',
            'temperature': 0.7,
            'max_tokens': None,
        },
        'api': {
            'llm_api_key': None,
            'llm_base_url': None,
            'llm_timeout': 60,
            'serpapi_api_key': None,
        },
        'system': {
            'debug': False,
            'log_level': 'INFO',
        },
        'memory': {
            'max_history_length': 10,
            'embedding_model': 'Qwen/Qwen3-Embedding-8B',
        },
        'tts': {
            'enabled': True,
            'engine': 'genie',
            'active_character': 'feibi',
            'language': 'zh',
            'server': {
                'host': '127.0.0.1',
                'port': 8001
            }
        }
    },
    'characters.json': {},
    'voice_storage.json': {}
}

class ConfigMigration:
    """
    负责配置文件的路径管理、初始化和迁移
    """
    
    def __init__(self, app_name: str = APP_NAME):
        self.app_name = app_name
        
        # 路径初始化
        self.project_root = Path(__file__).resolve().parent.parent  # backend/
        self.project_config_dir = self.project_root / "config"
        self.project_tts_dir = self.project_config_dir / "tts"
        self.project_memory_dir = self.project_root / "memory" / "store"
        
        self.docs_dir = self._get_documents_dir()
        self.app_docs_dir = self.docs_dir / self.app_name
        self.user_config_dir = self.app_docs_dir / "config"
        self.user_memory_dir = self.app_docs_dir / "memory"
        self.live2d_dir = self.app_docs_dir / "live2d"

    def _get_documents_dir(self) -> Path:
        """获取用户文档目录"""
        if platform.system() == "Windows":
            try:
                import ctypes.wintypes
                CSIDL_PERSONAL = 5       # My Documents
                SHGFP_TYPE_CURRENT = 0   # Get current, not default value
                buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
                ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buf)
                return Path(buf.value)
            except Exception:
                return Path.home() / "Documents"
        else:
            return Path.home() / "Documents"

    def ensure_directories(self):
        """确保所有必要的目录存在"""
        for directory in [self.user_config_dir, self.user_memory_dir, self.live2d_dir]:
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print(f"Error creating directory {directory}: {e}")

    def migrate_all(self):
        """执行所有迁移任务"""
        self.ensure_directories()
        # TODO: 未来实现完整的配置和记忆文件迁移功能
        # 当前临时禁用所有同步逻辑
        # self._migrate_config_files()
        # self._migrate_memory_files()
        pass

    def _migrate_config_files(self):
        """迁移配置文件"""
        # TODO: 未来实现配置文件迁移功能 - 从项目目录复制配置文件到用户目录
        # 当前临时禁用配置文件同步逻辑
        # 原功能：遍历 CONFIG_FILES，将项目配置目录的文件复制到用户配置目录
        # 原功能：对于 core_config.json，会进行智能合并，补充缺失的配置项
        pass

    def _migrate_memory_files(self):
        """迁移记忆文件"""
        # TODO: 未来实现记忆文件迁移功能 - 从项目记忆目录复制到用户记忆目录
        # 当前临时禁用记忆文件同步逻辑
        # 原功能：遍历项目记忆目录，将文件和子目录复制到用户记忆目录
        pass

    def _save_json(self, path: Path, data: Dict):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_config_path(self, filename: str) -> Path:
        """获取配置文件的最终路径 (用户目录优先)"""
        user_path = self.user_config_dir / filename
        if user_path.exists():
            return user_path
        
        project_path = self.project_config_dir / filename
        if project_path.exists():
            return project_path
            
        return user_path

# 单例实例，供 settings.py 使用
migration = ConfigMigration()
