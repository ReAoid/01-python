import os
import sys
import json
import shutil
import platform
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

# 尝试导入 config 定义
try:
    from backend.config import APP_NAME, CONFIG_FILES, DEFAULT_CONFIG_DATA
except ImportError:
    # 兼容在 backend 目录下直接运行的情况
    try:
        from config import APP_NAME, CONFIG_FILES, DEFAULT_CONFIG_DATA
    except ImportError:
        # 默认值
        APP_NAME = "AiAssistant"
        CONFIG_FILES = ['core_config.json']
        DEFAULT_CONFIG_DATA = {}

class ConfigManager:
    """
    跨平台配置文件管理器
    自动管理用户文档目录下的配置文件和记忆文件。
    支持配置迁移、自动创建目录等功能。
    遵循单例模式。
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, app_name: str = None):
        if self._initialized:
            return
            
        self.app_name = app_name or APP_NAME
        
        # 初始化目录路径
        self.docs_dir = self._get_documents_dir()
        self.app_docs_dir = self.docs_dir / self.app_name
        self.config_dir = self.app_docs_dir / "config"
        self.memory_dir = self.app_docs_dir / "memory"
        self.live2d_dir = self.app_docs_dir / "live2d"
        
        # 项目源码路径 (假设此文件在 backend/utils/config_manager.py)
        current_file = Path(__file__).resolve()
        self.project_root = current_file.parent.parent  # backend/
        self.project_config_dir = self.project_root / "config"
        self.project_memory_dir = self.project_root / "memory" / "store"
        
        self._initialized = True
        
        # 确保目录存在并迁移
        self.ensure_config_directory()
        self.migrate_config_files()

    def _get_documents_dir(self) -> Path:
        """获取用户文档目录"""
        if platform.system() == "Windows":
            import ctypes.wintypes
            CSIDL_PERSONAL = 5       # My Documents
            SHGFP_TYPE_CURRENT = 0   # Get current, not default value
            buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buf)
            return Path(buf.value)
        else:
            # macOS 和 Linux 通常都在 ~/Documents
            return Path.home() / "Documents"

    def ensure_config_directory(self) -> bool:
        """确保配置目录存在"""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            print(f"Error creating config directory: {e}")
            return False

    def ensure_memory_directory(self) -> bool:
        """确保记忆目录存在"""
        try:
            self.memory_dir.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            print(f"Error creating memory directory: {e}")
            return False
            
    def ensure_live2d_directory(self) -> bool:
        """确保 Live2D 目录存在"""
        try:
            self.live2d_dir.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            print(f"Error creating live2d directory: {e}")
            return False

    def get_config_path(self, filename: str) -> Path:
        """
        获取配置文件路径
        优先级: 用户文档 > 项目目录
        """
        user_path = self.config_dir / filename
        project_path = self.project_config_dir / filename
        
        if user_path.exists():
            return user_path
        if project_path.exists():
            return project_path
            
        return user_path

    def get_memory_path(self, filename: str) -> Path:
        """
        获取记忆文件路径
        优先级: 用户文档 > 项目目录
        """
        user_path = self.memory_dir / filename
        # 注意：项目目录结构可能是 backend/memory/store/filename
        project_path = self.project_memory_dir / filename
        
        if user_path.exists():
            return user_path
        if project_path.exists():
            return project_path
            
        return user_path

    def load_json_config(self, filename: str, default_value: Any = None) -> Dict:
        """加载 JSON 配置文件"""
        path = self.get_config_path(filename)
        
        try:
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            elif default_value is not None:
                return default_value
            else:
                # 如果文件不存在但有默认值定义在 constants 里，也可以返回那个
                # 这里简单处理，只返回传入的 default_value
                 raise FileNotFoundError(f"Config file not found: {filename}")
        except Exception as e:
            if default_value is not None:
                return default_value
            raise e

    def save_json_config(self, filename: str, data: Dict) -> None:
        """保存 JSON 配置文件"""
        self.ensure_config_directory()
        path = self.config_dir / filename
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def migrate_config_files(self) -> None:
        """迁移配置文件"""
        self.ensure_config_directory()
        
        for filename in CONFIG_FILES:
            target_path = self.config_dir / filename
            if target_path.exists():
                continue
                
            # 1. 尝试从项目目录复制
            src_path = self.project_config_dir / filename
            if src_path.exists():
                shutil.copy2(src_path, target_path)
                continue
                
            # 2. 使用默认配置创建
            if filename in DEFAULT_CONFIG_DATA:
                self.save_json_config(filename, DEFAULT_CONFIG_DATA[filename])

    def migrate_memory_files(self) -> None:
        """迁移记忆文件"""
        self.ensure_memory_directory()
        
        if not self.project_memory_dir.exists():
            return

        for item in self.project_memory_dir.glob('*'):
            target_path = self.memory_dir / item.name
            if not target_path.exists():
                if item.is_file():
                    shutil.copy2(item, target_path)
                elif item.is_dir():
                    shutil.copytree(item, target_path)

    def get_config_info(self) -> Dict:
        """获取配置信息"""
        return {
            'documents_dir': str(self.docs_dir),
            'app_dir': str(self.app_docs_dir),
            'config_dir': str(self.config_dir),
            'memory_dir': str(self.memory_dir),
            'live2d_dir': str(self.live2d_dir),
            'project_config_dir': str(self.project_config_dir),
            'project_memory_dir': str(self.project_memory_dir),
            'config_files': {f: str(self.get_config_path(f)) for f in CONFIG_FILES}
        }

    # --- 角色管理 API ---

    def load_characters(self, character_json_path=None) -> dict:
        """加载角色配置文件"""
        filename = character_json_path or 'characters.json'
        return self.load_json_config(filename, default_value={})

    def save_characters(self, data: dict, character_json_path=None) -> None:
        """保存角色配置文件"""
        filename = character_json_path or 'characters.json'
        self.save_json_config(filename, data)

    def get_character_data(self) -> tuple:
        """获取完整的角色元数据（占位实现，需根据实际数据结构调整）"""
        # 这里只是为了满足 API 签名，实际逻辑依赖于 characters.json 的结构
        chars = self.load_characters()
        # 假设结构
        master_name = chars.get('master', {}).get('name', 'Master')
        her_name = chars.get('current_character', 'AI')
        return (master_name, her_name, chars, {}, {}, {}, {}, {}, {}, {})

    # --- 音色管理 API ---

    def load_voice_storage(self) -> dict:
        """加载音色配置存储"""
        return self.load_json_config('voice_storage.json', default_value={})

    def save_voice_storage(self, data: dict) -> None:
        """保存音色配置存储"""
        self.save_json_config('voice_storage.json', data)

    # --- 核心配置 API ---

    def get_core_config(self) -> dict:
        """
        动态读取核心 API 配置
        整合了 core_config.json 和环境变量
        """
        json_config = self.load_json_config('core_config.json', default_value={})
        
        llm_cfg = json_config.get('llm', {})
        sys_cfg = json_config.get('system', {})
        mem_cfg = json_config.get('memory', {})
        api_cfg = json_config.get('api', {})
        
        def get_val(env_key, json_val, type_func=str):
            env_val = os.getenv(env_key)
            if env_val is not None:
                if type_func == bool:
                    return env_val.lower() == "true"
                return type_func(env_val)
            return json_val

        return {
            'LLM_MODEL_ID': get_val("LLM_MODEL_ID", llm_cfg.get('default_model')) or "gpt-3.5-turbo",
            'LLM_PROVIDER': get_val("LLM_PROVIDER", llm_cfg.get('default_provider')) or "openai",
            'LLM_API_KEY': get_val("LLM_API_KEY", api_cfg.get('llm_api_key')),
            'LLM_BASE_URL': get_val("LLM_BASE_URL", api_cfg.get('llm_base_url')),
            'LLM_TIMEOUT': get_val("LLM_TIMEOUT", api_cfg.get('llm_timeout'), int) or 60,
            'TEMPERATURE': get_val("TEMPERATURE", llm_cfg.get('temperature'), float) or 0.7,
            'MAX_TOKENS': get_val("MAX_TOKENS", llm_cfg.get('max_tokens'), int),
            'DEBUG': get_val("DEBUG", sys_cfg.get('debug'), bool) or False,
            'LOG_LEVEL': get_val("LOG_LEVEL", sys_cfg.get('log_level')) or "INFO",
            'MAX_HISTORY_LENGTH': get_val("MAX_HISTORY_LENGTH", mem_cfg.get('max_history_length'), int) or 100,
            'MEMORY_STORE_PATH': str(self.get_memory_path("memory_store.json")),
            'EMBEDDING_MODEL': get_val("EMBEDDING_MODEL", mem_cfg.get('embedding_model')) or "Qwen/Qwen3-Embedding-8B",
            'SERPAPI_API_KEY': get_val("SERPAPI_API_KEY", api_cfg.get('serpapi_api_key'))
        }
    
    def get_tts_config(self) -> dict:
        """
        获取 TTS 配置
        整合了 core_config.json 和环境变量
        """
        json_config = self.load_json_config('core_config.json', default_value={})
        tts_cfg = json_config.get('tts', {})
        server_cfg = tts_cfg.get('server', {})
        
        def get_val(env_key, json_val, type_func=str):
            env_val = os.getenv(env_key)
            if env_val is not None:
                if type_func == bool:
                    return env_val.lower() == "true"
                return type_func(env_val)
            return json_val
        
        # 处理 genie_data_dir 路径
        genie_data_dir = get_val("GENIE_DATA_DIR", tts_cfg.get('genie_data_dir'))
        if genie_data_dir and not Path(genie_data_dir).is_absolute():
            # 如果是相对路径，转换为绝对路径（相对于项目根目录）
            genie_data_dir = str(self.project_root / genie_data_dir)
        elif not genie_data_dir:
            # 如果没有配置，使用默认值
            genie_data_dir = str(self.project_root / 'config' / 'tts')
        
        return {
            'enabled': get_val("TTS_ENABLED", tts_cfg.get('enabled'), bool) or True,
            'engine': get_val("TTS_ENGINE", tts_cfg.get('engine')) or "genie",
            'genie_data_dir': genie_data_dir,
            'server_host': get_val("TTS_SERVER_HOST", server_cfg.get('host')) or "127.0.0.1",
            'server_port': get_val("TTS_SERVER_PORT", server_cfg.get('port'), int) or 8000,
            'auto_start': get_val("TTS_AUTO_START", server_cfg.get('auto_start'), bool) or False,
            'active_character': get_val("TTS_ACTIVE_CHARACTER", tts_cfg.get('active_character')) or "feibi",
            'language': get_val("TTS_LANGUAGE", tts_cfg.get('language')) or "zh"
        }


# 全局单例
_config_manager = None

def get_config_manager(app_name: str = None) -> ConfigManager:
    """获取配置管理器单例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(app_name)
    return _config_manager

# 便捷函数
def get_config_path(filename: str) -> Path:
    return get_config_manager().get_config_path(filename)

def load_json_config(filename: str, default_value: Any = None) -> Dict:
    return get_config_manager().load_json_config(filename, default_value)

def save_json_config(filename: str, data: Dict) -> None:
    return get_config_manager().save_json_config(filename, data)

def get_core_config() -> Dict:
    return get_config_manager().get_core_config()
