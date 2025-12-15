"""
Genie TTS 集成模块
提供 Genie TTS 客户端和可选的服务器管理功能
"""
import asyncio
import logging
import aiohttp
import os
import sys
from typing import Optional, AsyncIterator
from pathlib import Path

logger = logging.getLogger(__name__)


class GenieTTS:
    """
    Genie TTS 客户端
    通过 HTTP API 与 Genie TTS 服务器通信，实现流式语音合成
    """
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8000):
        """
        初始化 Genie TTS 客户端
        
        Args:
            host: Genie TTS 服务器地址
            port: Genie TTS 服务器端口
        """
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.session: Optional[aiohttp.ClientSession] = None
        self.character_name: Optional[str] = None
        self.is_ready = False
        
    async def connect(self, timeout: int = 10) -> bool:
        """
        连接到 Genie TTS 服务器并检查健康状态
        
        Args:
            timeout: 连接超时时间（秒）
            
        Returns:
            bool: 连接是否成功
        """
        if self.session is None:
            self.session = aiohttp.ClientSession()
        
        try:
            async with self.session.get(
                f"{self.base_url}/", 
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
        加载角色模型
        
        Args:
            character_name: 角色名称
            onnx_model_dir: ONNX 模型目录路径
            language: 语言代码（zh/en/jp）
            
        Returns:
            bool: 是否加载成功
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
        设置参考音频（必需步骤，用于音色克隆）
        
        Args:
            audio_path: 参考音频文件路径
            audio_text: 参考音频对应的文本
            language: 语言代码
            
        Returns:
            bool: 是否设置成功
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
        流式语音合成（异步生成器）
        
        Args:
            text: 要合成的文本
            split_sentence: 是否自动分句
            
        Yields:
            bytes: 音频数据块（PCM 格式，32kHz, mono, 16-bit）
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
            async with self.session.post(
                f"{self.base_url}/tts",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
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
            logger.info("Genie TTS 客户端已关闭")
    
    def __del__(self):
        """析构函数，确保资源被释放"""
        if self.session and not self.session.closed:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.close())
                else:
                    loop.run_until_complete(self.close())
            except Exception:
                pass


# ============================================================================
# 可选：Genie TTS 服务器管理功能（如果需要在代码中启动服务器）
# ============================================================================

def start_genie_server_standalone(
    host: str = "127.0.0.1", 
    port: int = 8000, 
    workers: int = 1,
    genie_data_dir: str = None
):
    """
    独立启动 Genie TTS 服务器（阻塞调用）
    通常在独立脚本中使用，不在主应用中调用
    
    Args:
        host: 服务器监听地址
        port: 服务器监听端口
        workers: 工作进程数量
        genie_data_dir: Genie 数据目录路径（可选，默认使用 backend/config/tts）
    """

    # 设置环境变量
    if genie_data_dir and os.path.exists(genie_data_dir):
        os.environ['GENIE_DATA_DIR'] = genie_data_dir
        logger.info(f"设置 GENIE_DATA_DIR={genie_data_dir}")
    elif not os.environ.get('GENIE_DATA_DIR'):
        # 如果没有指定，自动使用 backend/config/tts 作为默认位置
        default_data_dir = Path(__file__).parent.parent / 'config' / 'tts'
        default_data_dir.mkdir(parents=True, exist_ok=True)  # 确保目录存在
        os.environ['GENIE_DATA_DIR'] = str(default_data_dir)
        logger.info(f"自动设置 GENIE_DATA_DIR={default_data_dir}（首次启动会自动下载模型）")

    try:
        import genie_tts as genie
    except ImportError:
        print("错误: 未找到 genie_tts 模块")
        print("安装命令: pip install genie-tts")
        sys.exit(1)
    
    logger.info(f"启动 Genie TTS 服务器 {host}:{port} (workers={workers})...")
    
    try:
        genie.start_server(host=host, port=port, workers=workers)
    except KeyboardInterrupt:
        logger.info("收到停止信号，正在关闭服务器...")
    except Exception as e:
        logger.error(f"服务器启动失败: {e}")
        raise


# ============================================================================
# 命令行启动支持
# ============================================================================

if __name__ == "__main__":
    """
    独立运行模式 - 启动 Genie TTS 服务器
    用法: python genie_tts.py [--host HOST] [--port PORT]
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="启动 Genie TTS 服务器")
    parser.add_argument("--host", default="127.0.0.1", help="服务器监听地址")
    parser.add_argument("--port", type=int, default=8000, help="服务器监听端口")
    parser.add_argument("--workers", type=int, default=1, help="工作进程数量")
    parser.add_argument("--data-dir", help="Genie 数据目录路径")
    
    args = parser.parse_args()
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 启动服务器
    start_genie_server_standalone(
        host=args.host,
        port=args.port,
        workers=args.workers,
        genie_data_dir=args.data_dir
    )
