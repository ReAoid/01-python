"""
TTS 测试 API

提供 TTS 服务状态检测和语音生成测试功能
"""

import logging
import asyncio
import httpx
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from backend.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tts", tags=["TTS测试"])


# ============================================================================
# 请求/响应模型
# ============================================================================

class TTSTestRequest(BaseModel):
    """TTS 测试请求"""
    text: str = Field(..., min_length=1, max_length=500, description="要合成的文本")
    character: Optional[str] = Field(None, description="角色名称（可选，默认使用配置中的角色）")
    language: Optional[str] = Field(None, description="语言（可选，默认使用配置中的语言）")


# ============================================================================
# API 路由
# ============================================================================

@router.get("/status")
async def check_tts_status():
    """
    检查 TTS 服务状态
    
    Returns:
        服务状态信息
    """
    try:
        tts_config = settings.tts
        
        # 检查是否启用
        if not tts_config.enabled:
            return {
                "enabled": False,
                "running": False,
                "message": "TTS 服务未启用"
            }
        
        # 检查服务是否运行
        server_url = f"http://{tts_config.server.host}:{tts_config.server.port}"
        
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                # 尝试访问健康检查端点（假设 Genie TTS 有类似端点）
                # 如果没有，可以尝试访问根路径
                response = await client.get(f"{server_url}/")
                
                if response.status_code < 500:
                    return {
                        "enabled": True,
                        "running": True,
                        "server_url": server_url,
                        "engine": tts_config.engine,
                        "character": tts_config.active_character,
                        "language": tts_config.language,
                        "message": "TTS 服务运行正常"
                    }
                else:
                    return {
                        "enabled": True,
                        "running": False,
                        "server_url": server_url,
                        "message": f"TTS 服务响应异常: HTTP {response.status_code}"
                    }
        
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            return {
                "enabled": True,
                "running": False,
                "server_url": server_url,
                "message": f"无法连接到 TTS 服务: {type(e).__name__}",
                "hint": "请确保 TTS 服务已启动 (python backend/genie_server.py)"
            }
    
    except Exception as e:
        logger.error(f"检查 TTS 状态失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"检查 TTS 状态失败: {str(e)}")


@router.post("/test")
async def test_tts_synthesis(request: TTSTestRequest):
    """
    测试 TTS 语音合成
    
    Args:
        request: TTS 测试请求
    
    Returns:
        合成的音频数据（WAV 格式）
    """
    try:
        tts_config = settings.tts
        
        # 检查是否启用
        if not tts_config.enabled:
            raise HTTPException(status_code=503, detail="TTS 服务未启用")
        
        # 使用配置中的默认值或请求中的值
        character = request.character or tts_config.active_character
        language = request.language or tts_config.language
        
        # 构建 TTS 服务 URL
        server_url = f"http://{tts_config.server.host}:{tts_config.server.port}"
        
        # 调用 TTS 服务
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # 根据 Genie TTS 的 API 格式构建请求
                # 注意：这里需要根据实际的 Genie TTS API 调整
                tts_request_data = {
                    "text": request.text,
                    "character": character,
                    "language": language
                }
                
                # 假设 Genie TTS 有 /synthesize 端点
                response = await client.post(
                    f"{server_url}/synthesize",
                    json=tts_request_data
                )
                
                if response.status_code == 200:
                    # 返回音频数据
                    return Response(
                        content=response.content,
                        media_type="audio/wav",
                        headers={
                            "Content-Disposition": f"attachment; filename=tts_test_{character}.wav"
                        }
                    )
                else:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"TTS 服务返回错误: {response.text}"
                    )
        
        except httpx.ConnectError:
            raise HTTPException(
                status_code=503,
                detail="无法连接到 TTS 服务，请确保服务已启动"
            )
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=504,
                detail="TTS 服务响应超时"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TTS 测试失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"TTS 测试失败: {str(e)}")


@router.post("/test_local")
async def test_tts_local(request: TTSTestRequest):
    """
    使用本地 TTS 服务进行测试（直接调用 TTS 引擎）
    
    这个端点会直接使用 TTS 服务类进行合成，不依赖外部服务器
    
    Args:
        request: TTS 测试请求
    
    Returns:
        合成的音频数据（PCM 格式）
    """
    try:
        from backend.services.tts_service import TTSService
        from backend.config import settings
        import io
        
        # 创建 TTS 服务实例
        tts_service = TTSService(settings)
        
        # 用于收集音频数据的缓冲区
        audio_buffer = io.BytesIO()
        
        # 定义音频回调
        async def audio_callback(audio_data):
            if isinstance(audio_data, bytes):
                audio_buffer.write(audio_data)
        
        # 启动 TTS 服务
        await tts_service.start(audio_callback)
        
        try:
            # 推送文本进行合成
            await tts_service.push_text(request.text)
            
            # 等待合成完成（简单等待，实际应该有更好的同步机制）
            await asyncio.sleep(2.0)
            
            # 获取音频数据
            audio_data = audio_buffer.getvalue()
            
            if not audio_data:
                raise HTTPException(status_code=500, detail="未生成音频数据")
            
            return Response(
                content=audio_data,
                media_type="audio/wav",
                headers={
                    "Content-Disposition": f"attachment; filename=tts_test_local.wav"
                }
            )
        
        finally:
            # 停止 TTS 服务
            await tts_service.stop()
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"本地 TTS 测试失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"本地 TTS 测试失败: {str(e)}")


@router.get("/characters")
async def list_tts_characters():
    """
    列出可用的 TTS 角色
    
    Returns:
        可用角色列表
    """
    try:
        from backend.config import paths
        from pathlib import Path
        
        # TTS 角色目录
        tts_dir = paths.TTS_DIR / "GenieData" / "CharacterModels" / "v2ProPlus"
        
        if not tts_dir.exists():
            return {
                "characters": [],
                "message": "TTS 角色目录不存在"
            }
        
        # 扫描角色目录
        characters = []
        for char_dir in tts_dir.iterdir():
            if char_dir.is_dir():
                # 检查是否有必需的文件
                has_config = (char_dir / "prompt_wav.json").exists()
                has_models = (char_dir / "tts_models").exists()
                
                characters.append({
                    "name": char_dir.name,
                    "path": str(char_dir),
                    "has_config": has_config,
                    "has_models": has_models,
                    "ready": has_config and has_models
                })
        
        return {
            "characters": characters,
            "count": len(characters),
            "current": settings.tts.active_character
        }
    
    except Exception as e:
        logger.error(f"列出 TTS 角色失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"列出 TTS 角色失败: {str(e)}")
