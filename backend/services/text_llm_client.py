import asyncio
import logging
from typing import List, Dict, Optional
from backend.utils.openai_llm import OpenaiLlm
from backend.core.message import Message
from backend.config import settings
from backend.config.prompts import SYSTEM_PROMPT_DEFAULT_ASSISTANT

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

        # 6. 临时 RAG 上下文 (发完即焚)
        self.temp_rag_context: Optional[str] = None

    def _init_system_prompt(self, system_prompt: Optional[str]):
        """初始化 System Prompt"""
        system_content = system_prompt or SYSTEM_PROMPT_DEFAULT_ASSISTANT

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
            # 构造发送给 LLM 的消息列表 (不修改 self.history)
            messages_to_send = [self.system_message] + self.history

            # 如果有临时 RAG 上下文，注入到消息列表末尾 (在 User 消息之前或之后均可，通常 User 之后 System 之前效果较好)
            # 这里策略：插入在 System Prompt 之后，或者作为临时的 System Message 插入到最后
            if self.temp_rag_context:
                rag_msg = Message(
                    role="system", 
                    content=f"[Relevant Memory]\n{self.temp_rag_context}\n(Use this information to answer the user's question if relevant.)"
                )
                # 插入到倒数第二的位置 (即 User 消息之前) 或者直接 append 到最后
                # 直接 append 到最后通常效果最强，因为离生成最近
                messages_to_send.append(rag_msg)
                
            # 调用 OpenaiLlm 的异步流式接口
            async for chunk in self.llm.astream(messages_to_send):
                # 1. 放入队列供消费者使用
                await self.output_queue.put(chunk)

                full_response += chunk

            # 生成结束，添加 Sentinel (None) 表示结束
            await self.output_queue.put(None)

            # 更新历史 (只存真实的 Assistant 回复)
            self.history.append(Message(role="assistant", content=full_response))
            
            # [关键] 清除临时上下文
            self.temp_rag_context = None

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

    def set_previous_summary(self, summary: str):
        """注入上一轮会话的总结作为 Context"""
        if not summary:
            return
            
        context_msg = f"\n\n[Context from previous session]:\n{summary}\n"
        
        # 追加到 System Prompt 后面
        self.system_message.content += context_msg
        logger.info("Previous session summary injected into System Prompt.")

    def add_temporary_context(self, context: str):
        """
        设置临时 RAG 上下文。
        该上下文仅在下一次生成请求中有效，生成结束后立即清除，
        不会污染 self.history。
        """
        if not context:
            return
            
        self.temp_rag_context = context
        logger.debug("Temporary RAG context set (will be used in next generation only).")