"""
ASR 测试 API

提供 ASR 音频上传和识别测试功能
"""

import logging
import asyncio
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from backend.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/asr", tags=["ASR测试"])


# ============================================================================
# 请求/响应模型
# ============================================================================

class ASRTestResponse(BaseModel):
    """ASR 测试响应"""
    success: bool
    text: str = ""
    language: Optional[str] = None
    confidence: Optional[float] = None
    duration: Optional[float] = None
    message: Optional[str] = None


# ============================================================================
# API 路由
# ============================================================================

@router.get("/status")
async def check_asr_status():
    """
    检查 ASR 服务状态
    
    Returns:
        服务状态信息
    """
    try:
        asr_config = settings.asr
        
        # 检查是否启用
        if not asr_config.enabled:
            return {
                "enabled": False,
                "message": "ASR 服务未启用"
            }
        
        # 检查模型是否存在
        model_cache_dir = Path(asr_config.model_cache_dir) if asr_config.model_cache_dir else None
        
        model_status = {}
        if model_cache_dir and model_cache_dir.exists():
            # 检查 FunASR 模型目录
            models_dir = model_cache_dir / "models" / "iic"
            
            required_models = [
                "SenseVoiceSmall",  # ASR 模型
                "speech_fsmn_vad_zh-cn-16k-common-pytorch",  # VAD 模型
            ]
            
            for model_name in required_models:
                model_path = models_dir / model_name
                model_status[model_name] = {
                    "exists": model_path.exists(),
                    "path": str(model_path)
                }
        
        return {
            "enabled": True,
            "engine": asr_config.engine,
            "model": asr_config.model,
            "language": asr_config.language,
            "model_cache_dir": str(model_cache_dir) if model_cache_dir else None,
            "models": model_status,
            "message": "ASR 配置已加载"
        }
    
    except Exception as e:
        logger.error(f"检查 ASR 状态失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"检查 ASR 状态失败: {str(e)}")


@router.post("/test_upload")
async def test_asr_upload(
    file: UploadFile = File(..., description="音频文件（支持 WAV, MP3, M4A 等格式）")
) -> ASRTestResponse:
    """
    上传音频文件进行 ASR 测试
    
    Args:
        file: 音频文件
    
    Returns:
        识别结果
    """
    try:
        asr_config = settings.asr
        
        # 检查是否启用
        if not asr_config.enabled:
            raise HTTPException(status_code=503, detail="ASR 服务未启用")
        
        # 检查文件类型
        allowed_types = ["audio/wav", "audio/mpeg", "audio/mp3", "audio/x-m4a", "audio/mp4"]
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件类型: {file.content_type}，支持的类型: {', '.join(allowed_types)}"
            )
        
        # 保存临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        try:
            # 使用 ASR 引擎进行识别
            from backend.utils.asr.funasr_engine import FunASREngine
            
            # 创建 ASR 引擎实例
            engine = FunASREngine(
                model_cache_dir=asr_config.model_cache_dir,
                language=asr_config.language,
                vad_enabled=asr_config.vad_enabled,
                lid_enabled=asr_config.lid_enabled
            )
            
            # 初始化引擎
            await asyncio.to_thread(engine.initialize)
            
            # 识别音频
            result = await asyncio.to_thread(engine.transcribe_file, temp_file_path)
            
            if result and result.get("text"):
                return ASRTestResponse(
                    success=True,
                    text=result["text"],
                    language=result.get("language"),
                    confidence=result.get("confidence"),
                    duration=result.get("duration"),
                    message="识别成功"
                )
            else:
                return ASRTestResponse(
                    success=False,
                    message="未识别到有效语音"
                )
        
        finally:
            # 清理临时文件
            try:
                Path(temp_file_path).unlink()
            except:
                pass
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ASR 测试失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"ASR 测试失败: {str(e)}")


@router.post("/test_stream")
async def test_asr_stream():
    """
    测试 ASR 流式识别（WebSocket 或实时音频流）
    
    注意：此端点需要配合 WebSocket 使用
    """
    return {
        "message": "流式识别请通过 WebSocket 连接进行测试",
        "websocket_url": "/ws/chat",
        "instructions": "在聊天界面中点击麦克风按钮进行实时语音识别测试"
    }


@router.get("/models")
async def list_asr_models():
    """
    列出已安装的 ASR 模型
    
    Returns:
        模型列表
    """
    try:
        asr_config = settings.asr
        model_cache_dir = Path(asr_config.model_cache_dir) if asr_config.model_cache_dir else None
        
        if not model_cache_dir or not model_cache_dir.exists():
            return {
                "models": [],
                "message": "模型目录不存在"
            }
        
        # 扫描模型目录
        models_dir = model_cache_dir / "models" / "iic"
        
        if not models_dir.exists():
            return {
                "models": [],
                "message": "FunASR 模型目录不存在"
            }
        
        models = []
        for model_dir in models_dir.iterdir():
            if model_dir.is_dir():
                # 检查模型文件
                has_config = (model_dir / "config.yaml").exists()
                has_model = (model_dir / "model.pt").exists() or (model_dir / "model.onnx").exists()
                
                # 获取模型大小
                size = 0
                if model_dir.exists():
                    size = sum(f.stat().st_size for f in model_dir.rglob('*') if f.is_file())
                
                models.append({
                    "name": model_dir.name,
                    "path": str(model_dir),
                    "has_config": has_config,
                    "has_model": has_model,
                    "ready": has_config and has_model,
                    "size_mb": round(size / (1024 * 1024), 2)
                })
        
        return {
            "models": models,
            "count": len(models),
            "model_cache_dir": str(model_cache_dir)
        }
    
    except Exception as e:
        logger.error(f"列出 ASR 模型失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"列出 ASR 模型失败: {str(e)}")


@router.get("/supported_formats")
async def get_supported_formats():
    """
    获取支持的音频格式
    
    Returns:
        支持的格式列表
    """
    return {
        "formats": [
            {
                "extension": ".wav",
                "mime_type": "audio/wav",
                "description": "WAV 音频格式（推荐）"
            },
            {
                "extension": ".mp3",
                "mime_type": "audio/mpeg",
                "description": "MP3 音频格式"
            },
            {
                "extension": ".m4a",
                "mime_type": "audio/x-m4a",
                "description": "M4A 音频格式"
            },
            {
                "extension": ".mp4",
                "mime_type": "audio/mp4",
                "description": "MP4 音频格式"
            }
        ],
        "recommended": {
            "format": "WAV",
            "sample_rate": settings.asr.audio.sample_rate,
            "channels": settings.asr.audio.channels,
            "bit_depth": settings.asr.audio.sample_width * 8
        }
    }
