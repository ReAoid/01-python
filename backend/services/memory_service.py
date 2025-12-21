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
        
        # 订阅聊天完成事件
        event_bus.subscribe(EventType.CHAT_COMPLETED, self.handle_chat_completion)
        logger.info("记忆服务已初始化并订阅 CHAT_COMPLETED")

    async def handle_chat_completion(self, event: Event):
        """
        分析聊天内容以提取事实并更新记忆。
        """
        data = event.data
        user_content = data.get("user_content")
        ai_content = data.get("ai_content")
        
        if not user_content or not ai_content:
            return

        logger.info("记忆服务正在处理聊天完成事件...")

        # 1. 更新短期记忆 (滑动窗口)
        # 注意: Brain 可能会处理这个作为上下文，但 MemoryManager 需要它用于自己的记录
        self.memory_manager.add_interaction(user_content, ai_content)
        
        # 2. 提取事实 (异步)
        await self._extract_and_store_facts(user_content, ai_content)

    async def _extract_and_store_facts(self, user: str, ai: str):
        """
        使用 LLM 提取事实并存储到长期记忆中。
        """
        prompt = f"""
        Analyze the following interaction between User and AI.
        Extract key facts, user preferences, or important context that should be remembered for future conversations.
        If there are no new important facts, return "NO_FACTS".
        
        User: {user}
        AI: {ai}
        
        Output only the facts, concise and clear.
        """
        
        try:
            messages = [
                Message(role="system", content="You are a memory extraction system."),
                Message(role="user", content=prompt)
            ]
            
            response = await self.llm.agenerate(messages)
            content = response.content.strip()
            
            if content and "NO_FACTS" not in content:
                logger.info(f"提取到的事实: {content}")
                # 存储到向量存储
                # 注意: 现有代码中的 VectorStore add 目前是同步的。
                # 在真正的高负载系统中，我们会将其放入线程池或使其异步。
                # 目前，我们直接运行它，因为它在来自 EventBus 的异步任务包装器内。
                self.memory_manager.vector_store.add(content, metadata={"source": "extraction", "type": "fact"})
                
        except Exception as e:
            logger.error(f"事实提取出错: {e}")
