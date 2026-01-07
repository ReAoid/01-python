"""
TTS 引擎抽象基类。

定义统一的 TTS 引擎接口，所有具体实现都应继承此类。
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator
import logging

logger = logging.getLogger(__name__)


class BaseTTSEngine(ABC):
    """TTS 引擎抽象基类。"""

    @abstractmethod
    async def initialize(self) -> bool:
        """初始化 TTS 引擎（加载模型或建立连接）。

        Returns:
            bool: 初始化是否成功。
        """
        raise NotImplementedError

    @abstractmethod
    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        """流式语音合成。

        Args:
            text: 要合成的文本。

        Yields:
            bytes: PCM 音频数据块。
        """
        raise NotImplementedError

    @abstractmethod
    async def shutdown(self):
        """关闭引擎并释放资源。"""
        raise NotImplementedError

    async def clear_queue(self):
        """清空内部任务队列（可选实现）。"""
        # 默认不做任何事，由具体实现按需重写。
        return None
