from abc import ABC, abstractmethod
from typing import List, Generator
from backend.core.message import Message

class Llm(ABC):
    """Llm 基类"""

    @abstractmethod
    def generate(self, messages: List[Message], **kwargs) -> Message:
        """Generate a response from the LLM."""
        pass

    @abstractmethod
    def stream(self, messages: List[Message], **kwargs) -> Generator[str, None, None]:
        """Stream the response from the LLM."""
        pass
