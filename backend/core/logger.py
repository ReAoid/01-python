"""
日志配置模块
统一使用标准 logging API + 中央队列 + loguru 输出
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from queue import Queue
from threading import Lock
from typing import Optional

from loguru import logger as loguru_logger

SUCCESS_LEVEL_NUM = 25


def _ensure_success_level() -> None:
    if not hasattr(logging, "SUCCESS"):
        logging.SUCCESS = SUCCESS_LEVEL_NUM  # type: ignore[attr-defined]
        logging.addLevelName(SUCCESS_LEVEL_NUM, "SUCCESS")

        def success(self, message, *args, **kwargs):
            if self.isEnabledFor(SUCCESS_LEVEL_NUM):
                self._log(SUCCESS_LEVEL_NUM, message, args, **kwargs)

        logging.Logger.success = success  # type: ignore[assignment]


# 全局队列与监听器（单进程内统一使用）
_log_queue: Optional[Queue] = None
_queue_listener: Optional[logging.handlers.QueueListener] = None
_lock = Lock()


class LoguruHandler(logging.Handler):
    """将标准 logging 的 LogRecord 转发给 loguru"""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            # 使用 logging 的级别名称，保持与标准 logging 文本级别一致
            level = record.levelname

            # 使用 LogRecord 自带的位置信息
            extra = {
                "logger_name": record.name,
                "logger_func": record.funcName,
                "logger_line": record.lineno,
            }

            loguru_logger.bind(**extra).opt(
                exception=record.exc_info,
                depth=0,
            ).log(level, record.getMessage())
        except Exception:
            self.handleError(record)


def _configure_loguru_sinks(
    log_level: str,
    log_file: Optional[str],
    rotation: str,
    retention: str,
) -> None:
    """配置 loguru 的控制台/文件输出，并在启动时清空旧日志文件"""
    # 移除已有 sink
    loguru_logger.remove()

    # 控制台输出（彩色，美观格式）
    loguru_logger.add(
        sys.stderr,
        level=log_level.upper(),
        colorize=True,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{extra[logger_name]}</cyan>:<cyan>{extra[logger_func]}</cyan>:<cyan>{extra[logger_line]}</cyan> - "
            "<level>{message}</level>"
        ),
    )

    # 文件输出（单一总日志文件）
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # 启动时清空历史日志
        log_path.open("w").close()

        loguru_logger.add(
            str(log_path),
            level=log_level.upper(),
            format=(
                "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
                "{extra[logger_name]}:{extra[logger_func]}:{extra[logger_line]} - {message}"
            ),
            rotation=rotation,
            retention=retention,
            encoding="utf-8",
            mode="a",
        )


def init_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = "logs/app.log",
    rotation: str = "10 MB",
    retention: str = "7 days",
) -> None:
    """初始化统一日志系统

    - 所有 logging.getLogger(...) 的日志都通过中央队列
    - 队列消费者使用 loguru 同时输出到控制台和总日志文件
    """
    global _log_queue, _queue_listener

    with _lock:
        if _queue_listener is not None:
            # 已初始化，无需重复
            return

        _ensure_success_level()

        # 先配置 loguru sink（含启动时清空文件）
        _configure_loguru_sinks(log_level, log_file, rotation, retention)

        # 创建中央队列
        _log_queue = Queue()

        # 队列消费者：将 LogRecord 交给 loguru
        loguru_handler = LoguruHandler()
        _queue_listener = logging.handlers.QueueListener(
            _log_queue,
            loguru_handler,
            respect_handler_level=True,
        )
        _queue_listener.start()

        # 配置 root logger：仅挂 QueueHandler
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

        for h in root_logger.handlers[:]:
            root_logger.removeHandler(h)

        queue_handler = logging.handlers.QueueHandler(_log_queue)
        root_logger.addHandler(queue_handler)


def shutdown_logging() -> None:
    """优雅关闭日志系统，在应用退出时调用"""
    global _log_queue, _queue_listener

    with _lock:
        if _queue_listener is not None:
            _queue_listener.stop()
            _queue_listener = None

        _log_queue = None


# 向后兼容旧接口，内部统一转到 init_logging

def setup_logger(
    log_level: str = "INFO",
    log_file: Optional[str] = "logs/app.log",
    rotation: str = "10 MB",
    retention: str = "7 days",
):
    """兼容旧代码的入口，推荐使用 init_logging"""
    init_logging(log_level=log_level, log_file=log_file, rotation=rotation, retention=retention)
    return logging.getLogger(__name__)


def init_default_logger():
    """默认初始化，兼容旧接口"""
    init_logging()
    return logging.getLogger(__name__)
