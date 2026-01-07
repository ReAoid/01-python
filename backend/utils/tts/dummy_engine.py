"""
Dummy TTS 引擎实现。

用于测试和占位的空实现，不执行实际的语音合成。
"""

import logging
from typing import AsyncIterator

from .base_engine import BaseTTSEngine

logger = logging.getLogger(__name__)


class DummyTTSEngine(BaseTTSEngine):
    """Dummy TTS 引擎，仅用于测试或禁用 TTS 时占位。"""

    async def initialize(self) -> bool:
        logger.info("Dummy TTS 引擎初始化完成（不输出音频）")
        return True

    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        """不实际合成音频，仅记录日志。"""
        logger.debug(f"Dummy TTS 收到文本: {text!r}，不产生音频数据")
        if False:
            # 保持为异步生成器的形式
            yield b""

    async def shutdown(self):
        logger.info("Dummy TTS 引擎已关闭")

    async def clear_queue(self):
        logger.debug("Dummy TTS: 清空队列（无实际操作）")
        return None
