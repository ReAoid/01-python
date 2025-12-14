from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

from backend.core.llm import Llm
from backend.core.message import Message
from backend.utils.config_manager import get_core_config


class Agent(ABC):
    """Agent基类"""

    def __init__(
            self,
            name: str,
            llm: Llm,
            system_prompt: Optional[str] = None,
            config: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.llm = llm
        self.system_prompt = system_prompt
        # 使用 config_manager 读取配置，允许传入自定义配置覆盖
        self.config = config or get_core_config()
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
