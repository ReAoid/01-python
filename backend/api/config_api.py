"""
配置管理 API

提供配置的读取、更新和保存功能
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.config import paths, settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/config", tags=["配置管理"])


# ============================================================================
# 请求/响应模型
# ============================================================================

class LLMApiConfigUpdate(BaseModel):
    """LLM API 配置更新"""
    key: Optional[str] = None
    base_url: Optional[str] = None
    timeout: Optional[int] = None


class ChatLLMConfigUpdate(BaseModel):
    """聊天模型配置更新"""
    model: Optional[str] = None
    provider: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, gt=0)
    api: Optional[LLMApiConfigUpdate] = None


class EmbeddingLLMConfigUpdate(BaseModel):
    """嵌入模型配置更新"""
    model: Optional[str] = None
    api: Optional[LLMApiConfigUpdate] = None


class TTSServerConfigUpdate(BaseModel):
    """TTS 服务器配置更新"""
    host: Optional[str] = None
    port: Optional[int] = Field(None, gt=0, lt=65536)
    auto_start: Optional[bool] = None


class TTSConfigUpdate(BaseModel):
    """TTS 配置更新"""
    enabled: Optional[bool] = None
    engine: Optional[str] = None
    active_character: Optional[str] = None
    language: Optional[str] = None
    server: Optional[TTSServerConfigUpdate] = None


class ASRAudioConfigUpdate(BaseModel):
    """ASR 音频配置更新"""
    sample_rate: Optional[int] = Field(None, gt=0)
    channels: Optional[int] = Field(None, gt=0)
    sample_width: Optional[int] = Field(None, gt=0)


class ASRConfigUpdate(BaseModel):
    """ASR 配置更新"""
    enabled: Optional[bool] = None
    engine: Optional[str] = None
    model: Optional[str] = None
    language: Optional[str] = None
    audio: Optional[ASRAudioConfigUpdate] = None


class Live2DPositionConfigUpdate(BaseModel):
    """Live2D 位置配置更新"""
    x: Optional[int] = None
    y: Optional[int] = None
    max_x: Optional[int] = None
    max_y: Optional[int] = None


class Live2DConfigUpdate(BaseModel):
    """Live2D 配置更新"""
    enabled: Optional[bool] = None
    position: Optional[Live2DPositionConfigUpdate] = None


class ConfigUpdateRequest(BaseModel):
    """配置更新请求"""
    chat_llm: Optional[ChatLLMConfigUpdate] = None
    embedding_llm: Optional[EmbeddingLLMConfigUpdate] = None
    tts: Optional[TTSConfigUpdate] = None
    asr: Optional[ASRConfigUpdate] = None
    live2d: Optional[Live2DConfigUpdate] = None


# ============================================================================
# 辅助函数
# ============================================================================

def load_config_file() -> Dict[str, Any]:
    """加载配置文件"""
    config_path = paths.CONFIG_DIR / 'core_config.json'
    
    if not config_path.exists():
        raise HTTPException(status_code=404, detail="配置文件不存在")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"加载配置文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"加载配置文件失败: {str(e)}")


def save_config_file(config_data: Dict[str, Any]) -> None:
    """保存配置文件"""
    config_path = paths.CONFIG_DIR / 'core_config.json'
    
    try:
        # 备份原配置文件
        backup_path = paths.CONFIG_DIR / 'core_config.json.backup'
        if config_path.exists():
            import shutil
            shutil.copy2(config_path, backup_path)
        
        # 保存新配置
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        
        logger.info("配置文件已保存")
    except Exception as e:
        logger.error(f"保存配置文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"保存配置文件失败: {str(e)}")


def deep_update(base_dict: Dict, update_dict: Dict) -> Dict:
    """深度更新字典（递归合并）"""
    result = base_dict.copy()
    
    for key, value in update_dict.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_update(result[key], value)
        elif value is not None:  # 只更新非 None 的值
            result[key] = value
    
    return result


# ============================================================================
# API 路由
# ============================================================================

@router.get("/current")
async def get_current_config():
    """
    获取当前配置（从配置文件读取）
    
    Returns:
        完整的配置 JSON
    """
    try:
        config_data = load_config_file()
        
        # 确保 live2d 配置存在
        if 'live2d' not in config_data:
            config_data['live2d'] = {
                'enabled': False,
                'position': {
                    'x': 100,
                    'y': 500,
                    'max_x': 1920,
                    'max_y': 1080
                }
            }
        
        return config_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取配置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取配置失败: {str(e)}")


@router.put("/update")
async def update_config(update_request: ConfigUpdateRequest):
    """
    更新配置（部分更新）
    
    Args:
        update_request: 配置更新请求（只需要提供要更新的字段）
    
    Returns:
        更新后的完整配置
    """
    try:
        # 1. 加载当前配置
        current_config = load_config_file()
        
        # 2. 转换更新请求为字典（排除 None 值）
        update_data = update_request.model_dump(exclude_none=True)
        
        # 3. 深度合并配置
        updated_config = deep_update(current_config, update_data)
        
        # 4. 保存配置文件
        save_config_file(updated_config)
        
        logger.info(f"配置已更新: {list(update_data.keys())}")
        
        return {
            "success": True,
            "message": "配置已更新",
            "config": updated_config
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新配置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新配置失败: {str(e)}")


@router.post("/reset")
async def reset_config():
    """
    重置配置到默认值
    
    Returns:
        重置后的配置
    """
    try:
        default_config_path = paths.CONFIG_DIR / 'default_core_config.json'
        config_path = paths.CONFIG_DIR / 'core_config.json'
        
        if not default_config_path.exists():
            raise HTTPException(status_code=404, detail="默认配置文件不存在")
        
        # 读取默认配置
        with open(default_config_path, 'r', encoding='utf-8') as f:
            default_config = json.load(f)
        
        # 保存为当前配置
        save_config_file(default_config)
        
        logger.info("配置已重置为默认值")
        
        return {
            "success": True,
            "message": "配置已重置为默认值",
            "config": default_config
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重置配置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"重置配置失败: {str(e)}")


@router.get("/validate")
async def validate_config():
    """
    验证当前配置是否有效
    
    Returns:
        验证结果
    """
    try:
        config_data = load_config_file()
        
        # 基本验证
        issues = []
        
        # 检查必需字段
        required_sections = ['chat_llm', 'embedding_llm', 'system', 'memory', 'tts', 'asr']
        for section in required_sections:
            if section not in config_data:
                issues.append(f"缺少必需配置节: {section}")
        
        # 检查 LLM 配置
        if 'chat_llm' in config_data:
            chat_llm = config_data['chat_llm']
            if not chat_llm.get('model'):
                issues.append("chat_llm.model 不能为空")
            if not chat_llm.get('provider'):
                issues.append("chat_llm.provider 不能为空")
        
        # 检查嵌入模型配置
        if 'embedding_llm' in config_data:
            embedding_llm = config_data['embedding_llm']
            if not embedding_llm.get('model'):
                issues.append("embedding_llm.model 不能为空")
        
        is_valid = len(issues) == 0
        
        return {
            "valid": is_valid,
            "issues": issues,
            "message": "配置有效" if is_valid else f"配置存在 {len(issues)} 个问题"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"验证配置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"验证配置失败: {str(e)}")
