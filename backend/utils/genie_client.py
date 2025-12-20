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
    通过 HTTP API 与 Genie TTS 服务器通信，实现流式语音合成。
    
    Usage:
        client = GenieTTS(host="127.0.0.1", port=8001)
        if await client.connect():
            await client.load_character("feibi", "./models", "zh")
            await client.set_reference_audio("./ref.wav", "参考文本", "zh")
            
            async for chunk in client.synthesize_stream("你好"):
                # process audio chunk
                pass
    """
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8001):
        """
        初始化 Genie TTS 客户端。
        
        Args:
            host: Genie TTS 服务器地址 (default: "127.0.0.1")
            port: Genie TTS 服务器端口 (default: 8001)
        """
        # 1. 初始化配置
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"

        # 2. 初始化会话
        self.session: Optional[aiohttp.ClientSession] = None
        self.character_name: Optional[str] = None

        # 3. 初始化状态
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
    host: str = None, 
    port: int = None, 
    workers: int = 1,
    genie_data_dir: str = None
):
    """
    独立启动 Genie TTS 服务器（阻塞调用）
    通常在独立脚本中使用，不在主应用中调用
    
    Args:
        host: 服务器监听地址（默认从配置文件读取，回退到 127.0.0.1）
        port: 服务器监听端口（默认从配置文件读取，回退到 8001）
        workers: 工作进程数量
        genie_data_dir: Genie 数据目录路径（默认从配置文件读取，回退到 backend/config/tts）
    """
    
    # 读取配置
    try:
        from backend.config import settings
        
        # 使用配置文件的值作为默认值
        host = host or settings.tts.server.host
        port = port or settings.tts.server.port
        genie_data_dir = genie_data_dir or settings.tts.genie_data_dir
        
        logger.info(f"从配置文件加载 TTS 设置: host={host}, port={port}, data_dir={genie_data_dir}")
    except Exception as e:
        logger.warning(f"加载配置文件失败，使用默认值: {e}")
        # 回退到默认值
        host = host or '127.0.0.1'
        port = port or 8001
        # 如果没有配置，使用默认路径
        if not genie_data_dir:
            genie_data_dir = str(Path(__file__).parent.parent / 'config' / 'tts' / 'GenieData')

    # 设置环境变量（必须在导入 genie_tts 之前设置）
    if genie_data_dir:
        genie_data_path = Path(genie_data_dir)
        if not genie_data_path.is_absolute():
            # 如果是相对路径，转换为绝对路径（相对于项目根目录）
            project_root = Path(__file__).parent.parent.parent
            genie_data_path = project_root / genie_data_dir
        
        # 确保路径指向 GenieData 目录（如果配置的是父目录，自动加上 GenieData）
        if genie_data_path.name != 'GenieData':
            genie_data_path = genie_data_path / 'GenieData'
        
        os.environ['GENIE_DATA_DIR'] = str(genie_data_path.resolve())
        logger.info(f"设置 GENIE_DATA_DIR={genie_data_path.resolve()}")
    elif not os.environ.get('GENIE_DATA_DIR'):
        # 如果没有指定，自动使用 backend/config/tts/GenieData 作为默认位置
        default_data_dir = Path(__file__).parent.parent / 'config' / 'tts' / 'GenieData'
        os.environ['GENIE_DATA_DIR'] = str(default_data_dir.resolve())
        logger.info(f"自动设置 GENIE_DATA_DIR={default_data_dir.resolve()}（首次启动会自动下载模型）")
    
    # 检查 GenieData 目录是否存在，如果不存在则自动下载
    genie_data_path = Path(os.environ['GENIE_DATA_DIR'])
    if not genie_data_path.exists() or not (genie_data_path / 'chinese-hubert-base').exists():
        logger.warning("检测到 GenieData 不存在或不完整，正在自动下载...")
        try:
            # 先导入下载函数（这不会触发检查）
            from huggingface_hub import snapshot_download
        except ImportError:
            logger.error("错误: 未找到 huggingface_hub 模块")
            logger.error("安装命令: pip install huggingface-hub")
            sys.exit(1)
        
        try:
            logger.info("🚀 开始下载 Genie-TTS 资源... 这可能需要几分钟 ⏳")
            # 创建父目录
            genie_data_path.parent.mkdir(parents=True, exist_ok=True)
            # 下载到 tts 目录（HuggingFace 会自动创建 GenieData 子目录）
            snapshot_download(
                repo_id="High-Logic/Genie",
                repo_type="model",
                allow_patterns="GenieData/*",
                local_dir=str(genie_data_path.parent),
                local_dir_use_symlinks=False,
            )
            logger.info("✅ Genie-TTS 资源下载完成")
        except Exception as e:
            logger.error(f"下载 Genie-TTS 资源失败: {e}")
            logger.error("请手动下载或设置 GENIE_DATA_DIR 环境变量")
            sys.exit(1)

    try:
        import genie_tts as genie
    except ImportError:
        logger.error("错误: 未找到 genie_tts 模块")
        logger.error("安装命令: pip install genie-tts")
        sys.exit(1)
    except Exception as e:
        logger.error(f"导入 genie_tts 失败: {e}")
        raise

    # 检查 CharacterModels 是否存在，如果不存在则下载默认角色
    # 注意：genie_data_path 在上面已经定义
    character_models_path = genie_data_path / 'CharacterModels'
    if not character_models_path.exists():
        logger.info("未检测到角色模型目录，正在下载默认角色 'feibi'...")
        try:
            # load_predefined_character 会自动下载模型文件
            genie.load_predefined_character('feibi')
            logger.info("✓ 默认角色 'feibi' 下载完成")
        except Exception as e:
            logger.warning(f"下载默认角色失败: {e}")

    logger.info(f"启动 Genie TTS 服务器 {host}:{port} (workers={workers})...")
    
    # 设置信号处理器，确保优雅关闭
    import signal
    
    def signal_handler(sig, frame):
        """处理终止信号"""
        logger.info(f"\n收到信号 {sig}，正在关闭服务器...")
        try:
            # 调用 genie_tts 的停止方法（如果有）
            if hasattr(genie, 'stop'):
                genie.stop()
                logger.info("✓ 服务器已停止")
        except Exception as e:
            logger.error(f"停止服务器时出错: {e}")
        finally:
            sys.exit(0)
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # kill 命令
    
    try:
        logger.info("服务器正在运行，按 Ctrl+C 停止...")
        genie.start_server(host=host, port=port, workers=workers)
    except KeyboardInterrupt:
        logger.info("\n收到键盘中断，正在关闭服务器...")
        try:
            if hasattr(genie, 'stop'):
                genie.stop()
                logger.info("✓ 服务器已停止")
        except Exception as e:
            logger.error(f"停止服务器时出错: {e}")
    except Exception as e:
        logger.error(f"服务器运行失败: {e}")
        raise
    finally:
        logger.info("服务器已退出")


# ============================================================================
# 命令行启动支持
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 读取默认配置（用于帮助信息）
    default_host = "127.0.0.1"
    default_port = 8001
    default_data_dir = "backend/config/tts/GenieData"
    
    try:
        from backend.config import settings
        default_host = settings.tts.server.host
        default_port = settings.tts.server.port
        default_data_dir = settings.tts.genie_data_dir or default_data_dir
    except Exception:
        pass  # 忽略配置加载错误，使用硬编码默认值
    
    parser = argparse.ArgumentParser(
        description="启动 Genie TTS 服务器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
默认配置:
  host: {default_host}
  port: {default_port}
  data_dir: {default_data_dir}

配置来源优先级: 命令行参数 > 配置文件 > 环境变量 > 默认值
"""
    )
    parser.add_argument("--host", help=f"服务器监听地址 (默认: {default_host})")
    parser.add_argument("--port", type=int, help=f"服务器监听端口 (默认: {default_port})")
    parser.add_argument("--workers", type=int, default=1, help="工作进程数量 (默认: 1)")
    parser.add_argument("--data-dir", help=f"Genie 数据目录路径 (默认: {default_data_dir})")
    
    args = parser.parse_args()
    
    # 启动服务器（None 值会被 start_genie_server_standalone 自动处理）
    start_genie_server_standalone(
        host=args.host,
        port=args.port,
        workers=args.workers,
        genie_data_dir=args.data_dir
    )