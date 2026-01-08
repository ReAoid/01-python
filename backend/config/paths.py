"""路径配置模块

统一管理项目中所有路径配置。
所有运行时数据存储在 backend/data/ 目录下。
"""
import os
from pathlib import Path

# 定义应用名称
APP_NAME = "灵依"

# ============================================================================
# 核心路径定义
# ============================================================================

def get_project_root() -> Path:
    """获取项目根目录 (backend/)"""
    return Path(__file__).resolve().parent.parent

def get_data_dir() -> Path:
    """获取数据根目录 (backend/data/)"""
    return get_project_root() / "data"

def get_config_dir() -> Path:
    """获取配置目录 (backend/config/)"""
    return get_project_root() / "config"

def get_memory_dir() -> Path:
    """获取记忆存储目录 (backend/data/memory/)"""
    return get_data_dir() / "memory"

def get_logs_dir() -> Path:
    """获取日志目录 (backend/data/logs/)"""
    return get_data_dir() / "logs"

def get_tts_dir() -> Path:
    """获取 TTS 模型目录 (backend/data/tts/)"""
    return get_data_dir() / "tts"

def get_live2d_dir() -> Path:
    """获取 Live2D 模型目录 (backend/data/live2d/)"""
    return get_data_dir() / "live2d"

# ============================================================================
# 初始化：确保所有必要目录存在
# ============================================================================

def ensure_directories():
    """确保所有必要的数据目录存在"""
    directories = [
        get_data_dir(),
        get_memory_dir(),
        get_logs_dir(),
        get_tts_dir(),
        get_live2d_dir(),
        # 记忆子目录
        get_memory_dir() / "sessions",
        get_memory_dir() / "summaries",
        get_memory_dir() / "items",
        get_memory_dir() / "graph",
        get_memory_dir() / "categories",
    ]
    
    for directory in directories:
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"Error creating directory {directory}: {e}")

# ============================================================================
# 便捷常量（模块加载时初始化）
# ============================================================================

PROJECT_ROOT = get_project_root()
CONFIG_DIR = get_config_dir()
DATA_DIR = get_data_dir()
MEMORY_DIR = get_memory_dir()
LOGS_DIR = get_logs_dir()
TTS_DIR = get_tts_dir()
LIVE2D_DIR = get_live2d_dir()

# 自动初始化目录
ensure_directories()
