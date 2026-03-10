"""
有状态的异步 LLM 客户端

采用 "生产者-消费者" 模式，通过 asyncio.Queue 进行流式数据传输。
支持 skill 加载和工具链调用。
"""

import asyncio
import logging
from typing import List, Dict, Optional

from backend.services.llm_service import get_llm
from backend.core.message import Message
from backend.config import settings
from backend.config.prompts import SYSTEM_PROMPT_DEFAULT_ASSISTANT
from backend.utils.skills.loader import get_skill_loader

logger = logging.getLogger(__name__)


class LLMClient:
    """
    有状态的异步 LLM 客户端
    
    支持：
    - 流式输出
    - 对话历史管理
    - Skill 加载
    - 工具链调用（可选）
    """

    def __init__(
            self,
            system_prompt: Optional[str] = None,
            skill_name: Optional[str] = None,
            enable_tools: bool = True
    ):
        """
        初始化 LLM 客户端
        
        Args:
            system_prompt: 自定义系统提示词
            skill_name: 要加载的 skill 名称（如 "chat", "task"）
            enable_tools: 是否启用工具调用
        """
        # 1. 配置加载
        self.max_history = settings.memory.max_history_length

        # 2. 初始化 LLM
        self.llm = get_llm()

        # 3. 历史记录
        self.history: List[Message] = []

        # 4. 异步控制
        self.current_task: Optional[asyncio.Task] = None
        self.output_queue: asyncio.Queue = asyncio.Queue()

        # 5. Skill 加载
        self.skill_loader = get_skill_loader()
        self.skill_name = skill_name
        
        # 6. 初始化人设（结合 skill）
        self._init_system_prompt(system_prompt, skill_name)

        # 7. 临时 RAG 上下文
        self.temp_rag_context: Optional[str] = None
        
        # 8. 工具链处理器
        self.enable_tools = enable_tools
        self._tool_chain_handler = None
    
    def _init_system_prompt(self, system_prompt: Optional[str], skill_name: Optional[str]):
        """初始化系统提示词，结合 skill 内容"""
        base_prompt = system_prompt or SYSTEM_PROMPT_DEFAULT_ASSISTANT
        
        # 如果指定了 skill，加载 skill 内容
        if skill_name:
            skill_content = self.skill_loader.get_skill_prompt(skill_name)
            if skill_content:
                base_prompt = f"{base_prompt}\n\n{skill_content}"
                logger.info(f"已加载 Skill: {skill_name}")
        
        self.system_message = Message(role="system", content=base_prompt)
        self.clear_history()
    
    @property
    def tool_chain_handler(self):
        """延迟加载工具链处理器"""
        if self._tool_chain_handler is None and self.enable_tools:
            from backend.utils.llm.tool_chain_handler import ToolChainHandler
            self._tool_chain_handler = ToolChainHandler(
                llm=self.llm,
                max_iterations=10,
                on_tool_call=self._on_tool_call,
                on_tool_result=self._on_tool_result
            )
        return self._tool_chain_handler
    
    def _on_tool_call(self, tool_info):
        """工具调用回调"""
        logger.info(f"🔧 调用工具: {tool_info.name}")
    
    def _on_tool_result(self, tool_info):
        """工具结果回调"""
        logger.info(f"✅ 工具 {tool_info.name} 执行完成")

    def clear_history(self):
        """重置历史记录"""
        self.history = []
        logger.info("Conversation history cleared.")

    def _trim_history(self):
        """自动截断历史记录"""
        if len(self.history) > self.max_history:
            remove_count = len(self.history) - self.max_history
            self.history = self.history[-self.max_history:]
            logger.debug(f"History trimmed. Removed {remove_count} messages.")

    async def connect(self):
        """连接测试（可选）"""
        pass

    async def close(self):
        """关闭资源"""
        await self.cancel()

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
        发送用户消息，返回异步队列用于获取流式 Token
        
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
        """后台生成任务（生产者）- 支持工具调用"""
        full_response = ""
        try:
            # 构造发送给 LLM 的消息列表
            messages_to_send = list(self.history)

            # 如果有临时 RAG 上下文，注入到消息列表末尾
            if self.temp_rag_context:
                rag_msg = Message(
                    role="system", 
                    content=f"[Relevant Memory]\n{self.temp_rag_context}\n(Use this information to answer the user's question if relevant.)"
                )
                messages_to_send.append(rag_msg)
            
            # 检查是否启用工具链处理
            if self.enable_tools and self.tool_chain_handler:
                # 使用工具链处理器
                logger.info("使用工具链处理器处理请求")
                async for chunk in self.tool_chain_handler.process_with_tools(
                    messages=messages_to_send,
                    system_message=self.system_message
                ):
                    await self.output_queue.put(chunk)
                    full_response += chunk
            else:
                # 原有的流式生成逻辑
                all_messages = [self.system_message] + messages_to_send
                async for chunk in self.llm.astream(all_messages):
                    await self.output_queue.put(chunk)
                    full_response += chunk

            # 生成结束
            await self.output_queue.put(None)

            # 更新历史
            self.history.append(Message(role="assistant", content=full_response))
            
            # 清除临时上下文
            self.temp_rag_context = None

        except asyncio.CancelledError:
            logger.warning("Generation task was cancelled.")
            try:
                self.output_queue.put_nowait(None)
            except:
                pass
            raise

        except Exception as e:
            logger.error(f"Error in generation task: {e}")
            await self.output_queue.put(None)
            raise

    def get_history(self) -> List[Message]:
        """获取对话历史"""
        return self.history

    async def inject_history(self, history_dicts: List[Dict]):
        """注入历史记录（用于热重载）"""
        self.history = []
        for msg in history_dicts:
            if msg.get('role') != 'system':
                self.history.append(Message(role=msg['role'], content=msg['content']))

    def set_previous_summary(self, summary: str):
        """注入上一轮会话的总结作为 Context"""
        if not summary:
            return
            
        context_msg = f"\n\n[Context from previous session]:\n{summary}\n"
        self.system_message.content += context_msg
        logger.info("Previous session summary injected into System Prompt.")

    def add_temporary_context(self, context: str):
        """
        设置临时 RAG 上下文
        该上下文仅在下一次生成请求中有效
        """
        if not context:
            return
            
        self.temp_rag_context = context
        logger.debug("Temporary RAG context set.")
    
    def reload_skill(self, skill_name: str):
        """
        重新加载 skill
        
        Args:
            skill_name: skill 名称
        """
        self.skill_name = skill_name
        base_prompt = SYSTEM_PROMPT_DEFAULT_ASSISTANT
        
        skill_content = self.skill_loader.get_skill_prompt(skill_name)
        if skill_content:
            base_prompt = f"{base_prompt}\n\n{skill_content}"
            logger.info(f"重新加载 Skill: {skill_name}")
        
        self.system_message = Message(role="system", content=base_prompt)
