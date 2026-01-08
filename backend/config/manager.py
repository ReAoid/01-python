import json
from typing import Dict, Any, Tuple
from pathlib import Path

from . import paths

class ConfigManager:
    """
    数据文件管理器
    
    主要职责：
    1. 管理动态数据文件 (characters.json, voice_storage.json)
    2. 提供路径解析服务
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance

    @property
    def project_root(self) -> Path:
        return paths.PROJECT_ROOT

    def get_config_path(self, filename: str) -> Path:
        """获取配置文件路径"""
        return paths.CONFIG_DIR / filename
        
    def get_memory_path(self, filename: str) -> Path:
        """获取记忆文件路径"""
        return paths.MEMORY_DIR / filename
    
    def get_tts_base_dir(self) -> Path:
        """获取 TTS 基础目录"""
        return paths.TTS_DIR
    
    def ensure_live2d_directory(self) -> bool:
        """确保 Live2D 目录存在"""
        try:
            paths.LIVE2D_DIR.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            print(f"Error creating live2d directory: {e}")
            return False

    # --- 通用 JSON 文件操作 ---

    def load_json_file(self, filename: str, default: Any = None) -> Any:
        """加载 JSON 文件"""
        path = self.get_config_path(filename)
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading {filename}: {e}")
        return default if default is not None else {}

    def save_json_file(self, filename: str, data: Any):
        """保存 JSON 文件"""
        # TODO: 未来实现配置文件保存功能 - 将配置数据保存到用户目录
        # 当前临时禁用配置文件写入逻辑
        # 原功能：将 JSON 数据写入用户配置目录
        pass

    # --- 特定业务数据管理 ---

    def load_characters(self) -> Dict:
        return self.load_json_file('characters.json', {})

    def save_characters(self, data: Dict):
        self.save_json_file('characters.json', data)

    def load_voice_storage(self) -> Dict:
        return self.load_json_file('voice_storage.json', {})
    
    def save_voice_storage(self, data: Dict):
        self.save_json_file('voice_storage.json', data)

    def get_character_data(self) -> Tuple:
        """获取角色元数据"""
        chars = self.load_characters()
        master_name = chars.get('master', {}).get('name', 'Master')
        her_name = chars.get('current_character', 'AI')
        return (master_name, her_name, chars, {}, {}, {}, {}, {}, {}, {})

# 全局单例
config_manager = ConfigManager()

def get_config_manager(app_name: str = None) -> ConfigManager:
    return config_manager
