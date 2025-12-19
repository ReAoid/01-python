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
        self._migrate_config_files()
        self._migrate_memory_files()
        
        # 强制同步核心配置：如果项目目录下的配置比用户目录新，或者用户目录缺少关键 Key，可以在这里做更复杂的合并逻辑
        # 目前简单起见，如果项目配置存在，而用户配置也存在，我们尝试打印日志
        pass

    def _migrate_config_files(self):
        """迁移配置文件"""
        for filename in CONFIG_FILES:
            target_path = self.user_config_dir / filename
            
            # 1. 如果目标不存在，尝试复制或创建
            if not target_path.exists():
                src_path = self.project_config_dir / filename
                if src_path.exists():
                    shutil.copy2(src_path, target_path)
                    print(f"Copied default config to {target_path}")
                    continue
                
                if filename in DEFAULT_CONFIG_DATA:
                    self._save_json(target_path, DEFAULT_CONFIG_DATA[filename])
                    print(f"Created default config at {target_path}")
                    continue
            
            # 2. [关键修复] 如果是核心配置，强制检查是否为空或者是否需要更新
            # 这是一个简单的“覆盖更新”策略，仅当用户文件内容明显缺失时使用
            # 在开发环境中，我们希望项目目录下的 config 修改能生效
            # 但在生产环境中，我们希望保留用户的修改
            
            if filename == 'core_config.json':
                src_path = self.project_config_dir / filename
                if src_path.exists():
                    try:
                        with open(src_path, 'r', encoding='utf-8') as f:
                            project_data = json.load(f)
                        with open(target_path, 'r', encoding='utf-8') as f:
                            user_data = json.load(f)
                        
                        # 检查 key 是否缺失
                        changed = False
                        
                        # 递归检查 api 配置
                        if 'api' in project_data:
                            if 'api' not in user_data:
                                user_data['api'] = project_data['api']
                                changed = True
                            else:
                                for k, v in project_data['api'].items():
                                    if k not in user_data['api'] or not user_data['api'][k]:
                                        # 如果用户没填，或者 key 不存在，用项目的
                                        if v: # 只有当项目配置有值时才覆盖
                                            user_data['api'][k] = v
                                            changed = True
                        
                        if changed:
                            self._save_json(target_path, user_data)
                            print(f"Updated config at {target_path} with missing keys")
                            
                    except Exception as e:
                        print(f"Error merging config: {e}")

    def _migrate_memory_files(self):
        """迁移记忆文件"""
        if not self.project_memory_dir.exists():
            return

        for item in self.project_memory_dir.glob('*'):
            target_path = self.user_memory_dir / item.name
            if not target_path.exists():
                if item.is_file():
                    shutil.copy2(item, target_path)
                elif item.is_dir():
                    shutil.copytree(item, target_path)

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
