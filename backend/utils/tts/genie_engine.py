"""
基于 GenieTTS 的 TTS 引擎实现。

在子进程中使用，通过 HTTP 与本地 Genie TTS 服务通信，提供流式语音合成功能。
包含内部 HTTP 客户端和引擎封装层。
"""

import asyncio
import logging
import aiohttp
from typing import AsyncIterator, Dict, Any, Optional

from .base_engine import BaseTTSEngine

logger = logging.getLogger(__name__)


# ============================================================================
# Genie TTS HTTP 客户端（内部类）
# ============================================================================

class _GenieTTSClient:
    """
    Genie TTS HTTP 客户端（内部使用）
    
    通过 HTTP API 与本地 Genie TTS 服务器通信，实现流式语音合成。
    该类仅供 GenieTTSEngine 内部使用，不对外暴露。
    """
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8001):
        """
        初始化 Genie TTS 客户端。
        
        Args:
            host: Genie TTS 服务器地址 (default: "127.0.0.1")
            port: Genie TTS 服务器端口 (default: 8001)
        """
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.session: Optional[aiohttp.ClientSession] = None
        self.character_name: Optional[str] = None
        self.is_ready = False
        
    async def connect(self, timeout: int = 10) -> bool:
        """
        连接到 Genie TTS 服务器并检查健康状态。
        
        Args:
            timeout: 连接超时时间（秒）。默认为 10 秒。
            
        Returns:
            bool: 连接是否成功。成功返回 True，失败返回 False。
        """
        if self.session is None:
            self.session = aiohttp.ClientSession()
        
        try:
            # 使用 /docs 端点作为健康检查，这比 / 更可靠
            async with self.session.get(
                f"{self.base_url}/docs", 
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                if response.status == 200:
                    logger.info(f"✓ 成功连接到 Genie TTS 服务器: {self.base_url}")
                    return True
                else:
                    logger.error(f"✗ Genie TTS 服务器返回错误状态码: {response.status}")
                    return False
        except asyncio.TimeoutError:
            logger.error(f"✗ 连接 Genie TTS 服务器超时: {self.base_url}")
            return False
        except aiohttp.ClientError as e:
            logger.error(f"✗ 连接 Genie TTS 服务器失败: {e}")
            return False
    
    async def load_character(
        self, 
        character_name: str, 
        onnx_model_dir: str, 
        language: str = "zh"
    ) -> bool:
        """
        加载指定角色的 TTS 模型。
        
        Args:
            character_name: 角色名称（作为唯一标识符）。
            onnx_model_dir: ONNX 模型文件的目录路径。
            language: 语言代码（支持 'zh', 'en', 'jp'）。默认为 'zh'。
            
        Returns:
            bool: 是否加载成功。
        """
        if self.session is None:
            logger.error("客户端未连接，请先调用 connect()")
            return False
        
        payload = {
            "character_name": character_name,
            "onnx_model_dir": onnx_model_dir,
            "language": language
        }
        
        try:
            async with self.session.post(
                f"{self.base_url}/load_character",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    self.character_name = character_name
                    logger.info(f"✓ 成功加载角色 '{character_name}': {result}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"✗ 加载角色失败 (状态码 {response.status}): {error_text}")
                    return False
        except Exception as e:
            logger.error(f"✗ 加载角色时发生异常: {e}")
            return False
    
    async def set_reference_audio(
        self, 
        audio_path: str, 
        audio_text: str, 
        language: str = "zh"
    ) -> bool:
        """
        设置参考音频（用于 Zero-shot 音色克隆）。
        
        必须在 load_character 之后调用。
        
        Args:
            audio_path: 参考音频文件的绝对路径。
            audio_text: 参考音频对应的文本内容。
            language: 参考音频的语言代码。默认为 'zh'。
            
        Returns:
            bool: 是否设置成功。
        """
        if self.session is None or self.character_name is None:
            logger.error("请先连接并加载角色")
            return False
        
        payload = {
            "character_name": self.character_name,
            "audio_path": audio_path,
            "audio_text": audio_text,
            "language": language
        }
        
        try:
            async with self.session.post(
                f"{self.base_url}/set_reference_audio",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    self.is_ready = True
                    logger.info(f"✓ 成功设置参考音频: {result}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"✗ 设置参考音频失败 (状态码 {response.status}): {error_text}")
                    return False
        except Exception as e:
            logger.error(f"✗ 设置参考音频时发生异常: {e}")
            return False
    
    async def synthesize_stream(
        self, 
        text: str, 
        split_sentence: bool = True
    ) -> AsyncIterator[bytes]:
        """
        流式语音合成（异步生成器）。
        
        将文本发送给服务器，并异步接收返回的 PCM 音频数据块。
        
        Args:
            text: 要合成的文本内容。
            split_sentence: 是否让服务器自动进行分句处理。默认为 True。
            
        Yields:
            bytes: 音频数据块（PCM 格式，32kHz, mono, 16-bit）。
        """
        if not self.is_ready:
            logger.error("TTS 未就绪，请先完成角色加载和参考音频设置")
            return
        
        if not text or not text.strip():
            logger.warning("合成文本为空，跳过")
            return
        
        payload = {
            "character_name": self.character_name,
            "text": text,
            "split_sentence": split_sentence
        }
        
        try:
            # 设置更长的超时时间，避免连接中断 (total=60, connect=10, sock_read=30)
            timeout = aiohttp.ClientTimeout(total=60, connect=10, sock_read=30)
            
            async with self.session.post(
                f"{self.base_url}/tts",
                json=payload,
                timeout=timeout
            ) as response:
                if response.status == 200:
                    # 流式读取音频数据
                    chunk_count = 0
                    async for chunk in response.content.iter_chunked(1024):
                        if chunk:
                            chunk_count += 1
                            yield chunk
                    logger.debug(f"✓ 完成合成，共接收 {chunk_count} 个音频块")
                else:
                    error_text = await response.text()
                    logger.error(f"✗ TTS 合成失败 (状态码 {response.status}): {error_text}")
        except asyncio.TimeoutError:
            logger.error("✗ TTS 合成超时")
        except Exception as e:
            logger.error(f"✗ TTS 合成时发生异常: {e}")
    
    async def close(self):
        """关闭客户端连接"""
        if self.session:
            await self.session.close()
            self.session = None
            self.is_ready = False
            logger.debug("Genie TTS 客户端连接已关闭")


# ============================================================================
# TTS 引擎封装
# ============================================================================

class GenieTTSEngine(BaseTTSEngine):
    """Genie TTS 引擎实现。"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client: _GenieTTSClient | None = None

    async def initialize(self) -> bool:
        """初始化 Genie TTS 引擎并连接到本地服务。"""
        host = self.config.get("host", "127.0.0.1")
        port = self.config.get("port", 8001)
        self.client = _GenieTTSClient(host=host, port=port)

        logger.info(f"正在连接到 Genie TTS {host}:{port}...")
        if not await self.client.connect(timeout=10):
            logger.error("无法连接到 Genie TTS 服务器")
            logger.error("请确保已启动 Genie TTS 服务：python backend/genie_server.py")
            return False

        character = self.config.get("character")
        model_dir = self.config.get("model_dir")
        language = self.config.get("language", "zh")

        if character and model_dir:
            logger.info(f"正在加载角色: {character}")
            if not await self.client.load_character(character, model_dir, language):
                logger.error("加载角色失败")
                return False

        ref_audio_path = self.config.get("reference_audio_path")
        ref_audio_text = self.config.get("reference_audio_text")

        if ref_audio_path and ref_audio_text:
            logger.info(f"正在设置参考音频: {ref_audio_path}")
            if not await self.client.set_reference_audio(ref_audio_path, ref_audio_text, language):
                logger.error("设置参考音频失败")
                return False

        logger.info("✅ GenieTTSEngine 初始化完成")
        return True

    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        """调用 Genie TTS 进行流式语音合成。"""
        if not self.client:
            logger.error("GenieTTSEngine 未初始化")
            return
        if not text:
            return

        async for chunk in self.client.synthesize_stream(text):
            yield chunk

    async def shutdown(self):
        """关闭引擎并释放资源。"""
        if self.client:
            await self.client.close()
            self.client = None
        logger.info("GenieTTSEngine 已关闭")

    async def clear_queue(self):
        """当前引擎无内部队列，这里仅保留接口以保持一致性。"""
        return None
