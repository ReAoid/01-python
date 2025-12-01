from abc import ABC, abstractmethod
from typing import List, Generator
from backend.core.message import Message


class Llm(ABC):
    """Llm 基类"""

    @abstractmethod
    def generate(self, messages: List[Message], **kwargs) -> Message:
        """
        非流式生成响应,返回完整的消息。
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数(如 temperature, max_tokens 等)
            
        Returns:
            Message: 完整的响应消息
        """
        pass

    @abstractmethod
    def stream(self, messages: List[Message], **kwargs) -> Generator[str, None, None]:
        """
        流式生成响应。
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数(如 temperature, max_tokens 等)
            
        Yields:
            str: 流式生成的文本片段
        """
        pass
