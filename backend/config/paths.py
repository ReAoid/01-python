import os
import platform
import sys
from pathlib import Path

# 定义应用名称
APP_NAME = "灵依"

def get_project_root() -> Path:
    """获取项目根目录 (backend/)"""
    # 假设此文件在 backend/config/paths.py
    return Path(__file__).resolve().parent.parent

def get_user_documents_dir() -> Path:
    """获取跨平台的用户文档目录"""
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

def get_app_data_dir() -> Path:
    """获取应用数据主目录"""
    return get_user_documents_dir() / APP_NAME

def get_user_config_dir() -> Path:
    """获取用户配置目录"""
    return get_app_data_dir() / "config"

def get_user_memory_dir() -> Path:
    """获取用户记忆存储目录"""
    return get_app_data_dir() / "memory"

def get_user_live2d_dir() -> Path:
    """获取 Live2D 模型目录"""
    return get_app_data_dir() / "live2d"

# 项目内置默认配置目录
PROJECT_ROOT = get_project_root()
PROJECT_CONFIG_DIR = PROJECT_ROOT / "config"
PROJECT_MEMORY_DIR = PROJECT_ROOT / "memory" / "store"
