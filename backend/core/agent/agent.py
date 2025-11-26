from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
import json

from backend.core.llm.llm_interface import LLMInterface
from backend.core.memory.message import Message, SystemMessage, UserMessage, AssistantMessage, ToolMessage
from backend.core.tools.registry import ToolRegistry
from backend.core.logger.log_system import logger
from backend.core.config import Config

class Agent(ABC):
    """Agent基类"""

    def __init__(
        self,
        name: str,
        llm: LLMInterface,
        system_prompt: Optional[str] = None,
        config: Optional[Config] = None
    ):
        self.name = name
        self.llm = llm
        self.system_prompt = system_prompt
        self.config = config or Config()
        self._history: List[Message] = []

    @abstractmethod
    def run(self, input_text: str, **kwargs) -> str:
        """运行Agent"""
        pass

    def add_message(self, message: Message):
        """添加消息到历史记录"""
        self._history.append(message)

    def clear_history(self):
        """清空历史记录"""
        self._history.clear()

    def get_history(self) -> List[Message]:
        """获取历史记录"""
        return self._history.copy()

    def __str__(self) -> str:
        return f"Agent(name={self.name}, provider={self.llm.__class__.__name__})"
