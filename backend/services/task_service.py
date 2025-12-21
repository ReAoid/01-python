import logging
import asyncio
from backend.core.event_bus import event_bus, Event, EventType
from backend.utils.openai_llm import OpenaiLlm
from backend.core.message import Message

logger = logging.getLogger(__name__)

class TaskService:
    """
    分析用户意图并执行后台任务。
    "做事"服务器。
    """
    def __init__(self):
        self.llm = OpenaiLlm()
        event_bus.subscribe(EventType.CHAT_COMPLETED, self.handle_chat_analysis)
        logger.info("任务服务已初始化。")

    async def handle_chat_analysis(self, event: Event):
        user_content = event.data.get("user_content")
        
        if not user_content:
            return
            
        # 分析潜在意图
        await self._analyze_intent(user_content)

    async def _analyze_intent(self, text: str):
        prompt = f"""
        Analyze the user's input for any latent actionable tasks that can be performed in the background.
        Examples: "I wish I knew more about Python" -> Research Python.
        "Remind me to buy milk" -> Set reminder.
        
        User Input: "{text}"
        
        If there is a clear task, describe it in JSON format: {{ "task": "description", "action": "research|reminder|..." }}.
        If no task, return "NO_TASK".
        """
        
        try:
            messages = [
                Message(role="system", content="You are a background task analyzer."),
                Message(role="user", content=prompt)
            ]
            
            response = await self.llm.agenerate(messages)
            content = response.content.strip()
            
            if content and "NO_TASK" not in content:
                logger.info(f"检测到潜在任务: {content}")
                
                # 模拟执行
                asyncio.create_task(self._execute_task(content))
                
        except Exception as e:
            logger.error(f"任务分析出错: {e}")

    async def _execute_task(self, task_description: str):
        """
        模拟执行任务。
        """
        logger.info(f"开始后台执行: {task_description}")
        
        # 模拟工作
        await asyncio.sleep(5) 
        
        result = f"Finished background task based on your interest: {task_description}"
        
        # 通知系统/用户
        await event_bus.publish(EventType.TASK_COMPLETED, {
            "result": result,
            "original_task": task_description
        })
