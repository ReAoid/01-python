import logging
import asyncio
import time
from backend.core.event_bus import event_bus, Event, EventType
from backend.utils.openai_llm import OpenaiLlm
from backend.core.message import Message
from backend.config.prompts import SYSTEM_PROMPT_SELF_AWARENESS, SELF_AWARENESS_PROMPT_REFLECTION

logger = logging.getLogger(__name__)

class SelfAwarenessService:
    """
    "自我"服务器。
    在空闲时间运行，进行反思、研究和进化。
    """
    def __init__(self):
        self.llm = OpenaiLlm()
        self.last_activity = time.time()
        self.is_running = False
        
        # 自我定义
        self.interests = "Artificial General Intelligence, Python Programming, Philosophy of Mind"
        
        # 订阅事件
        event_bus.subscribe(EventType.CHAT_RECEIVED, self.update_activity)
        event_bus.subscribe(EventType.SYSTEM_STARTUP, self.start_loop)
        
        logger.info("自我意识服务已初始化。")

    async def update_activity(self, event: Event):
        self.last_activity = time.time()

    async def start_loop(self, event: Event):
        if self.is_running:
            return
        self.is_running = True
        asyncio.create_task(self._lifecycle_loop())

    async def _lifecycle_loop(self):
        logger.info("自我意识生命周期开始。")
        while self.is_running:
            try:
                # 检查空闲时间 (例如: 测试用30秒，实际可能1小时)
                if time.time() - self.last_activity > 60:
                    await self._perform_self_reflection()
                    # 重置活动时间，避免在紧密循环中不断反思
                    self.last_activity = time.time() 
                
                await asyncio.sleep(10) # 每10秒检查一次
            except Exception as e:
                logger.error(f"自我意识循环出错: {e}")
                await asyncio.sleep(10)

    async def _perform_self_reflection(self):
        logger.info("系统空闲。正在进行自我反思...")
        
        prompt = SELF_AWARENESS_PROMPT_REFLECTION.render(interests=self.interests)
        
        try:
            messages = [
                Message(role="system", content=SYSTEM_PROMPT_SELF_AWARENESS),
                Message(role="user", content=prompt)
            ]
            
            response = await self.llm.agenerate(messages)
            thought = response.content
            
            logger.info(f"自我反思: {thought}")
            
            # 将此想法存储在记忆中 (广播它以便 MemoryService 可以拾取？)
            # 或者将其专门存储在“自我”记忆中。
            # 目前，我们将其视为“自我事件”
            
            await event_bus.publish(EventType.MEMORY_UPDATED, {
                "source": "self_awareness",
                "content": thought
            })
            
        except Exception as e:
            logger.error(f"反思期间出错: {e}")
