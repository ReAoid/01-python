"""
日志配置模块
使用 loguru 进行统一日志管理
"""

import sys
from loguru import logger
from pathlib import Path


def setup_logger(
    log_level: str = "INFO",
    log_file: str = None,
    rotation: str = "10 MB",
    retention: str = "7 days"
):
    """
    配置全局日志
    
    Args:
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
        log_file: 日志文件路径,如果为 None 则只输出到控制台
        rotation: 日志文件轮转大小
        retention: 日志文件保留时间
    """
    # 移除默认的 handler
    logger.remove()
    
    # 添加控制台输出 (彩色格式)
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=log_level,
        colorize=True
    )
    
    # 如果指定了日志文件,添加文件输出
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.add(
            log_file,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level=log_level,
            rotation=rotation,
            retention=retention,
            encoding="utf-8",
            enqueue=True  # 异步写入,避免阻塞
        )
        
        logger.info(f"日志文件已配置: {log_file}")
    
    return logger


# 默认配置 (可在应用启动时调用)
def init_default_logger():
    """初始化默认日志配置"""
    return setup_logger(
        log_level="INFO",
        log_file="logs/app.log",
        rotation="10 MB",
        retention="7 days"
    )

