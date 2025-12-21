import logging
import asyncio
from backend.core.event_bus import event_bus, Event, EventType
from backend.utils.memory.memory_manager import MemoryManager
from backend.utils.openai_llm import OpenaiLlm
from backend.core.message import Message
from backend.config import settings

logger = logging.getLogger(__name__)

class MemoryService:
    def __init__(self):
        self.llm = OpenaiLlm()
        self.memory_manager = MemoryManager(llm=self.llm)
        
        # [优化] 移除 CHAT_COMPLETED 监听
        # 现在由 SessionManager 在热切换时主动调用 summarize_session
        logger.info("记忆服务已初始化 (被动模式)")

    # 之前的方法已移除，MemoryService 现在主要作为 MemoryManager 的服务层封装
    # 未来可以在这里添加更多高级的记忆编排逻辑
