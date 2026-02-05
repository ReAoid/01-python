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

# 添加根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


def ensure_genie_data(genie_data_dir: Optional[str] = None) -> Path:
    """
    检查 GenieData 目录及其必要的子目录是否存在。
    如果不存在，引导用户运行安装脚本。
    返回 GenieData 的绝对路径。
    
    Args:
        genie_data_dir: Genie 数据目录路径（可选）
        
    Returns:
        Path: GenieData 目录的绝对路径
        
    Raises:
        FileNotFoundError: 当 GenieData 目录不存在或不完整时
    """
    # 确定 genie_data_dir
    if genie_data_dir:
        genie_data_path = Path(genie_data_dir)
        if not genie_data_path.is_absolute():
             # 如果是相对路径，转换为绝对路径（相对于根目录）
            root_dir = Path(__file__).parent.parent
            genie_data_path = root_dir / genie_data_dir
        
        # 确保路径指向 GenieData 目录（如果配置的是父目录，自动加上 GenieData）
        if genie_data_path.name != 'GenieData':
             genie_data_path = genie_data_path / 'GenieData'
    else:
        # 如果没有指定，自动使用 backend/data/tts/GenieData 作为默认位置
        if os.environ.get('GENIE_DATA_DIR'):
            genie_data_path = Path(os.environ['GENIE_DATA_DIR'])
        else:
            # 使用统一的 paths 模块获取 TTS 目录
            from backend.config import paths
            default_data_dir = paths.TTS_DIR / 'GenieData'
            genie_data_path = default_data_dir
    
    # 设置环境变量（因为 genie_tts 库可能会用到）
    os.environ['GENIE_DATA_DIR'] = str(genie_data_path.resolve())
    logger.info(f"使用 GENIE_DATA_DIR={genie_data_path.resolve()}")
    
    # 检查 GenieData 目录是否存在
    if not genie_data_path.exists():
        logger.error("="*60)
        logger.error("❌ GenieData 目录不存在")
        logger.error(f"路径: {genie_data_path}")
        logger.error("")
        logger.error("📦 请先安装 TTS 模型：")
        logger.error("   python all_ready.py --tts-only")
        logger.error("")
        logger.error("或者手动下载模型：")
        logger.error("   1. 访问: https://huggingface.co/High-Logic/Genie")
        logger.error("   2. 下载 GenieData 目录")
        logger.error(f"   3. 放置到: {genie_data_path}")
        logger.error("="*60)
        raise FileNotFoundError(f"GenieData 目录不存在: {genie_data_path}")
    
    # 检查 chinese-hubert-base 是否存在
    hubert_path = genie_data_path / 'chinese-hubert-base'
    if not hubert_path.exists():
        logger.error("="*60)
        logger.error("❌ GenieData 不完整，缺少 chinese-hubert-base 模型")
        logger.error(f"路径: {hubert_path}")
        logger.error("")
        logger.error("🔧 请重新安装 TTS 模型：")
        logger.error("   python all_ready.py --tts-only --force")
        logger.error("")
        logger.error("或者手动下载：")
        logger.error("   从 https://huggingface.co/High-Logic/Genie 下载完整的 GenieData")
        logger.error("="*60)
        raise FileNotFoundError(f"chinese-hubert-base 模型不存在: {hubert_path}")
    
    # 检查 CharacterModels（警告但不中断）
    character_models_path = genie_data_path / 'CharacterModels'
    if not character_models_path.exists():
        logger.warning("="*60)
        logger.warning("⚠️  未检测到角色模型目录")
        logger.warning(f"路径: {character_models_path}")
        logger.warning("")
        logger.warning("建议安装角色模型：")
        logger.warning("   python all_ready.py --tts-only --force")
        logger.warning("")
        logger.warning("或者手动下载角色模型：")
        logger.warning("   从 https://huggingface.co/High-Logic/Genie 下载 CharacterModels")
        logger.warning("")
        logger.warning("注意: TTS 服务可能需要角色模型才能正常工作")
        logger.warning("="*60)
    else:
        logger.info(f"✓ CharacterModels 目录存在: {character_models_path}")
    
    logger.info(f"✅ GenieData 检查完成: {genie_data_path.resolve()}")
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
