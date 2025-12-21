import asyncio
import logging
from typing import Dict, List, Callable, Awaitable, Any
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

class EventType(str, Enum):
    # 聊天事件
    CHAT_RECEIVED = "chat.received"      # 收到用户输入
    CHAT_COMPLETED = "chat.completed"    # 一轮对话完成 (用户 + AI)
    
    # 系统事件
    SYSTEM_STARTUP = "system.startup"    # 系统启动
    SYSTEM_SHUTDOWN = "system.shutdown"  # 系统关闭
    
    # 记忆事件
    MEMORY_UPDATED = "memory.updated"    # 记忆已更新
    
    # 任务事件
    TASK_DETECTED = "task.detected"      # 检测到潜在任务
    TASK_COMPLETED = "task.completed"    # 任务执行完成

@dataclass
class Event:
    type: EventType
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)

class EventBus:
    """
    异步事件总线，用于组件解耦。
    允许服务订阅事件，而发布者无需知道订阅者的存在。
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EventBus, cls).__new__(cls)
            cls._instance.subscribers: Dict[EventType, List[Callable[[Event], Awaitable[None]]]] = {}
        return cls._instance

    def subscribe(self, event_type: EventType, callback: Callable[[Event], Awaitable[None]]):
        """注册特定事件类型的回调函数。"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)
        logger.info(f"已订阅 {event_type}: {callback.__name__}")

    async def publish(self, event_type: EventType, data: Dict[str, Any]):
        """向所有订阅者发布事件。"""
        event = Event(type=event_type, data=data)
        
        if event_type in self.subscribers:
            # 创建所有订阅者的任务以便并行运行
            tasks = []
            for callback in self.subscribers[event_type]:
                try:
                    tasks.append(asyncio.create_task(callback(event)))
                except Exception as e:
                    logger.error(f"为 {event_type} 准备订阅者任务时出错: {e}")
            
            if tasks:
                # 并发运行所有订阅者回调，且不严重阻塞发布者
                # 我们使用 return_exceptions=True 的 gather 来防止一个失败停止其他任务
                # 但如果想要“发后即忘”，我们不严格等待。
                # 理想情况下，我们等待它们以确保运行，或者只是生成它们。
                # 对于本系统，我们生成它们且不严重阻塞主流程。
                background_task = asyncio.create_task(self._run_subscribers(tasks, event_type))

    async def _run_subscribers(self, tasks, event_type):
        """辅助方法：等待订阅者完成并记录错误。"""
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in results:
            if isinstance(res, Exception):
                logger.error(f"订阅者处理 {event_type} 时出错: {res}")

# 全局实例
event_bus = EventBus()
