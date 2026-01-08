#!/usr/bin/env python
"""
Genie TTS 服务器启动脚本

独立启动 Genie TTS 本地服务器，提供 HTTP API 供 TTS 引擎调用。
通常在主应用启动前独立运行，或通过进程管理工具自动启动。

Usage:
    # 使用默认配置启动
    python backend/genie_server.py
    
    # 自定义配置启动
    python backend/genie_server.py --host 0.0.0.0 --port 8001 --workers 2
"""

import argparse
import logging
import os
import sys
import signal
from pathlib import Path
from typing import Optional

from backend.core.logger import init_logging, shutdown_logging

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


def ensure_genie_data(genie_data_dir: Optional[str] = None) -> Path:
    """
    确保 GenieData 目录及其必要的子目录（包括 CharacterModels）存在。
    如果不存在，则尝试下载。
    返回 GenieData 的绝对路径。
    
    Args:
        genie_data_dir: Genie 数据目录路径（可选）
        
    Returns:
        Path: GenieData 目录的绝对路径
    """
    # 确定 genie_data_dir
    if genie_data_dir:
        genie_data_path = Path(genie_data_dir)
        if not genie_data_path.is_absolute():
             # 如果是相对路径，转换为绝对路径（相对于项目根目录）
            project_root = Path(__file__).parent.parent
            genie_data_path = project_root / genie_data_dir
        
        # 确保路径指向 GenieData 目录（如果配置的是父目录，自动加上 GenieData）
        if genie_data_path.name != 'GenieData':
             genie_data_path = genie_data_path / 'GenieData'
    else:
        # 如果没有指定，自动使用 backend/config/tts/GenieData 作为默认位置
        if os.environ.get('GENIE_DATA_DIR'):
            genie_data_path = Path(os.environ['GENIE_DATA_DIR'])
        else:
            default_data_dir = Path(__file__).parent / 'config' / 'tts' / 'GenieData'
            genie_data_path = default_data_dir
    
    # 设置环境变量（因为 genie_tts 库可能会用到）
    os.environ['GENIE_DATA_DIR'] = str(genie_data_path.resolve())
    logger.info(f"使用 GENIE_DATA_DIR={genie_data_path.resolve()}")
    
    # 检查 GenieData/chinese-hubert-base
    if not genie_data_path.exists() or not (genie_data_path / 'chinese-hubert-base').exists():
        logger.warning(f"检测到 GenieData 不存在或不完整 ({genie_data_path})，正在自动下载...")
        try:
             from huggingface_hub import snapshot_download
        except ImportError:
             logger.error("错误: 未找到 huggingface_hub 模块")
             logger.error("安装命令: pip install huggingface-hub")
             raise ImportError("huggingface_hub module not found")

        try:
            logger.info("🚀 开始下载 Genie-TTS 资源... 这可能需要几分钟 ⏳")
            genie_data_path.parent.mkdir(parents=True, exist_ok=True)
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
            raise

    # 检查 CharacterModels
    try:
        import genie_tts as genie
        character_models_path = genie_data_path / 'CharacterModels'
        if not character_models_path.exists():
            logger.info("未检测到角色模型目录，正在下载默认角色 'feibi'...")
            try:
                genie.load_predefined_character('feibi')
                logger.info("✓ 默认角色 'feibi' 下载完成")
            except Exception as e:
                logger.warning(f"下载默认角色失败: {e}")
    except ImportError:
         logger.warning("未找到 genie_tts 模块，跳过 CharacterModels 检查")
    except Exception as e:
         logger.warning(f"检查 CharacterModels 时出错: {e}")

    return genie_data_path.resolve()


def start_genie_tts_server(
    host: str = None,
    port: int = None,
    workers: int = 1,
    genie_data_dir: str = None
):
    """
    启动 Genie TTS 服务器（阻塞调用）
    
    Args:
        host: 服务器监听地址（默认从配置文件读取，回退到 127.0.0.1）
        port: 服务器监听端口（默认从配置文件读取，回退到 8001）
        workers: 工作进程数量（默认 1）
        genie_data_dir: Genie 数据目录路径（默认从配置文件读取）
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
    
    # 确保数据目录存在并设置环境变量
    try:
        ensure_genie_data(genie_data_dir)
    except Exception as e:
        logger.error(f"初始化 GenieData 失败: {e}")
        sys.exit(1)

    # 导入 genie_tts 库
    try:
        import genie_tts as genie
    except ImportError:
        logger.error("错误: 未找到 genie_tts 模块")
        logger.error("安装命令: pip install genie-tts")
        sys.exit(1)
    except Exception as e:
        logger.error(f"导入 genie_tts 失败: {e}")
        raise

    logger.info(f"🚀 启动 Genie TTS 服务器 {host}:{port} (workers={workers})...")
    
    # 设置信号处理器，确保优雅关闭
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
        logger.info("✓ 服务器正在运行，按 Ctrl+C 停止...")
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


if __name__ == "__main__":
    # 配置日志（中央队列 + loguru + Genie 专用日志文件）
    from backend.config import paths
    init_logging(
        log_level="INFO",
        log_file=str(paths.LOGS_DIR / "genie.log"),
        rotation="10 MB",
        retention="7 days",
    )

    # 读取默认配置（用于帮助信息）
    default_host = "127.0.0.1"
    default_port = 8001
    
    try:
        from backend.config import settings, paths
        default_host = settings.tts.server.host
        default_port = settings.tts.server.port
        default_data_dir = settings.tts.genie_data_dir or str(paths.TTS_DIR / "GenieData")
    except Exception:
        default_data_dir = "backend/data/tts/GenieData"  # fallback
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description="启动 Genie TTS 本地服务器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
示例:
  # 使用默认配置启动
  python backend/genie_server.py
  
  # 自定义端口启动
  python backend/genie_server.py --port 8002
  
  # 多进程模式启动
  python backend/genie_server.py --workers 4

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
    
    try:
        # 启动服务器（None 值会被函数自动处理）
        start_genie_tts_server(
            host=args.host,
            port=args.port,
            workers=args.workers,
            genie_data_dir=args.data_dir
        )
    finally:
        # 确保日志队列线程优雅关闭
        shutdown_logging()
