"""
日志配置模块
统一使用标准 logging API + 中央队列 + loguru 输出
"""

import logging
import logging.handlers
import sys
import asyncio
from pathlib import Path
from queue import Queue
from threading import Lock
from typing import Optional
from datetime import datetime

from loguru import logger as loguru_logger


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


class WebSocketLogHandler(logging.Handler):
    """
    将日志通过事件总线推送到前端 WebSocket。
    只推送 INFO 及以上级别的日志，避免前端被 DEBUG 信息洪水。
    """
    
    def __init__(self, level=logging.INFO):
        super().__init__(level)
        # 延迟导入避免循环依赖
        self._event_bus = None
    
    @property
    def event_bus(self):
        if self._event_bus is None:
            from backend.core.event_bus import event_bus, EventType
            self._event_bus = event_bus
            self._EventType = EventType
        return self._event_bus
    
    def emit(self, record: logging.LogRecord) -> None:
        try:
            # 只推送 INFO 及以上级别
            if record.levelno < logging.INFO:
                return
            
            # 构造日志条目
            log_entry = {
                'level': record.levelname,
                'timestamp': datetime.now().isoformat(),
                'module': record.name,
                'function': record.funcName,
                'line': record.lineno,
                'message': record.getMessage(),
                'trace': self.format(record) if record.exc_info else None
            }
            
            # 通过事件总线异步推送
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(
                        self.event_bus.publish(self._EventType.LOG_ENTRY, log_entry)
                    )
            except RuntimeError:
                # 如果没有运行中的事件循环，忽略
                pass
        except Exception:
            # 静默失败，不影响主日志系统
            pass


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

        # 配置 root logger：同时挂载 QueueHandler 和 WebSocketLogHandler
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

        for h in root_logger.handlers[:]:
            root_logger.removeHandler(h)

        queue_handler = logging.handlers.QueueHandler(_log_queue)
        root_logger.addHandler(queue_handler)
        
        # 添加 WebSocket 日志推送 handler
        ws_handler = WebSocketLogHandler(level=logging.INFO)
        root_logger.addHandler(ws_handler)


def shutdown_logging() -> None:
    """优雅关闭日志系统，在应用退出时调用"""
    global _log_queue, _queue_listener

    with _lock:
        if _queue_listener is not None:
            _queue_listener.stop()
            _queue_listener = None

        _log_queue = None


