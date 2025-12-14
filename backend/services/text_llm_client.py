import asyncio
import logging
from typing import List, Dict, Optional, Callable
from backend.services.openai_llm import OpenaiLlm
from backend.core.message import Message

logger = logging.getLogger(__name__)

class TextLLMClient:
    """
    适配器：将无状态的 OpenaiLlm 封装为有状态的会话客户端
    """
    def __init__(self, api_key: str, on_token: Optional[Callable] = None, on_complete: Optional[Callable] = None):
        self.api_key = api_key
        self.on_token = on_token
        self.on_complete = on_complete
        
        # 内部使用 OpenaiLlm
        self.llm = OpenaiLlm(api_key=api_key)
        self.history: List[Message] = []
        
        # 简单的系统提示词
        self.history.append(Message(role="system", content="You are a helpful AI assistant."))

    async def connect(self):
        # 可以在这里做连通性测试
        pass

    async def close(self):
        # 清理资源
        pass
    
    async def cancel(self):
        # 取消当前的生成任务
        pass

    def get_history(self) -> List[Message]:
        return self.history

    async def inject_history(self, history_dicts: List[Dict]):
        """注入历史记录（用于热重载）"""
        for msg in history_dicts:
            self.history.append(Message(role=msg['role'], content=msg['content']))

    async def send_user_message(self, text: str):
        """发送用户消息并触发流式回调"""
        self.history.append(Message(role="user", content=text))
        
        full_response = ""
        
        # 注意: OpenaiLlm.stream 是同步生成器，这里为了简单直接在 async 方法里调用
        # 生产环境建议用 run_in_executor 避免阻塞 loop
        try:
            # 模拟异步调用同步的 stream
            loop = asyncio.get_running_loop()
            
            def _generate():
                return list(self.llm.stream(self.history))
            
            # 这里一次性拿回所有 chunk 是为了避免复杂的多线程迭代，
            # 实际应当在线程中迭代并 callback 回主线程
            # 为了演示逻辑，这里简化处理:
            
            # 临时方案：直接同步迭代（会阻塞）
            for chunk in self.llm.stream(self.history):
                if self.on_token:
                    if asyncio.iscoroutinefunction(self.on_token):
                        await self.on_token(chunk)
                    else:
                        self.on_token(chunk)
                full_response += chunk
                # 让出控制权，避免完全卡死
                await asyncio.sleep(0)

            self.history.append(Message(role="assistant", content=full_response))
            
            if self.on_complete:
                if asyncio.iscoroutinefunction(self.on_complete):
                    await self.on_complete()
                else:
                    self.on_complete()

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
