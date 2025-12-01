from typing import List, Dict, Optional
from loguru import logger
from backend.core.message import Message

class ShortTermMemory:
    """
    短期记忆管理（滑动窗口）。
    维护最近的对话历史。

    TODO: [功能增强]
    1. Token 限制：实现基于 Token 数量的限制，而不仅仅是消息数量 (max_messages)，以更精确地适配 LLM 上下文窗口限制。
    """

    def __init__(self, max_messages: int = 20):
        """
        初始化短期记忆。

        Args:
            max_messages: 保留的最大消息数量
        """
        self.max_messages = max_messages
        self.messages: List[Message] = []

    def add(self, role: str, content: str):
        """
        添加消息。

        Args:
            role: 角色 (user, assistant, system)
            content: 内容
        """
        msg = Message(role=role, content=content)
        self.messages.append(msg)
        self._prune()

    def add_message(self, message: Message):
        """直接添加 Message 对象"""
        self.messages.append(message)
        self._prune()

    def _prune(self):
        """
        修剪消息列表，保持在限制范围内

        TODO: [逻辑优化]
        1. 保护机制：智能修剪，不要移除 System Prompt (通常在 index 0) 或被标记为"关键"的消息。
        2. 记忆压缩：在移除消息前，使用 LLM 对即将移除的对话进行摘要 (Summarization)，并将摘要作为新的上下文插入或存入长期记忆 (参考 N.E.K.O 的 CompressedRecentHistoryManager)。
        """
        if len(self.messages) > self.max_messages:
            # 简单策略：移除最早的消息（通常保留第一个System Prompt是更好的做法，但在Manager层处理更好）
            # 这里先简单移除
            removed = self.messages.pop(0)
            logger.debug(f"短期记忆已修剪，移除: {removed.content[:20]}...")

    def get_messages(self) -> List[Message]:
        """获取所有消息"""
        return self.messages

    def get_context_text(self) -> str:
        """获取文本格式的上下文"""
        return "\n".join([f"{msg.role}: {msg.content}" for msg in self.messages])

    def clear(self):
        """清空记忆"""
        self.messages = []

