import asyncio
import logging
from typing import List, Dict, Optional
from backend.utils.openai_llm import OpenaiLlm
from backend.core.message import Message
from backend.config import settings

logger = logging.getLogger(__name__)


class TextLLMClient:
    """
    有状态的异步 LLM 客户端
    采用 "生产者-消费者" 模式，通过 asyncio.Queue 进行流式数据传输。
    """

    def __init__(
            self,
            system_prompt: Optional[str] = None
    ):
        # 1. 配置加载
        self.max_history = settings.memory.max_history_length

        # 2. 初始化 LLM
        self.llm = OpenaiLlm()

        # 3. 历史记录
        self.history: List[Message] = []

        # 4. 异步控制
        self.current_task: Optional[asyncio.Task] = None
        self.output_queue: asyncio.Queue = asyncio.Queue()

        # 5. 初始化人设
        self._init_system_prompt(system_prompt)

    def _init_system_prompt(self, system_prompt: Optional[str]):
        """初始化 System Prompt"""
        system_content = system_prompt

        # 如果未传入，直接使用默认值
        if not system_content:
            system_content = "You are a helpful AI assistant."

        # 6. 初始化系统消息
        self.system_message = Message(role="system", content=system_content)
        self.clear_history()

    def clear_history(self):
        """重置历史记录"""
        self.history = []
        logger.info("Conversation history cleared.")

    def _trim_history(self):
        """
        自动截断历史记录
        """
        if len(self.history) > self.max_history:
            remove_count = len(self.history) - self.max_history
            self.history = self.history[-self.max_history:]
            logger.debug(f"History trimmed. Removed {remove_count} messages.")

    async def connect(self):
        """连接测试 (可选)"""
        pass

    async def close(self):
        """关闭资源"""
        await self.cancel()
        pass

    async def cancel(self):
        """取消当前的生成任务"""
        if self.current_task and not self.current_task.done():
            logger.info("Cancelling current generation task...")
            self.current_task.cancel()
            try:
                await self.current_task
            except asyncio.CancelledError:
                logger.info("Task cancelled successfully.")
            except Exception as e:
                logger.error(f"Error during cancellation: {e}")
            finally:
                self.current_task = None

    async def send_user_message(self, text: str) -> asyncio.Queue:
        """
        发送用户消息，返回一个异步队列用于获取流式 Token。
        
        Usage:
            queue = await client.send_user_message("Hello")
            while True:
                token = await queue.get()
                if token is None: break
                print(token)
        """
        # 1. 停止之前的任务
        await self.cancel()

        # 2. 更新历史
        self.history.append(Message(role="user", content=text))
        self._trim_history()

        # 3. 创建新队列
        self.output_queue = asyncio.Queue()

        # 4. 启动生成任务
        self.current_task = asyncio.create_task(self._generate_task())

        return self.output_queue

    async def _generate_task(self):
        """后台生成任务 (生产者)"""
        full_response = ""
        try:
            # 调用 OpenaiLlm 的异步流式接口
            messages = [self.system_message] + self.history
            async for chunk in self.llm.astream(messages):
                # 1. 放入队列供消费者使用
                await self.output_queue.put(chunk)

                full_response += chunk

            # 生成结束，添加 Sentinel (None) 表示结束
            await self.output_queue.put(None)

            # 更新历史
            self.history.append(Message(role="assistant", content=full_response))

        except asyncio.CancelledError:
            logger.warning("Generation task was cancelled.")
            # 取消也放入 None 以终止消费者的循环
            try:
                self.output_queue.put_nowait(None)
            except:
                pass
            raise

        except Exception as e:
            logger.error(f"Error in generation task: {e}")
            # 发生异常时，向队列放入 None 以终止消费者的循环
            await self.output_queue.put(None)
            raise

    def get_history(self) -> List[Message]:
        return self.history

    async def inject_history(self, history_dicts: List[Dict]):
        """注入历史记录（用于热重载）"""
        self.history = []  # 重置
        for msg in history_dicts:
            if msg.get('role') != 'system':  # 避免重复 System
                self.history.append(Message(role=msg['role'], content=msg['content']))
