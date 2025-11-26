from abc import ABC, abstractmethod
from typing import List, Generator, Union, Dict, Any
from backend.core.memory.message import Message

class LLMInterface(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate(self, messages: List[Message], **kwargs) -> Message:
        """Generate a response from the LLM."""
        pass

    @abstractmethod
    def stream(self, messages: List[Message], **kwargs) -> Generator[str, None, None]:
        """Stream the response from the LLM."""
        pass
