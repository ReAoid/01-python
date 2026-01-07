"""
TTS Worker 模块

从原 tts_service 中抽取出的子进程逻辑，负责在独立进程中调用具体 TTS 引擎进行流式合成。
"""

import asyncio
import logging
import traceback
from multiprocessing import Queue
from typing import Dict, Any

from backend.utils.tts.base_engine import BaseTTSEngine
from backend.utils.tts.dummy_engine import DummyTTSEngine
from backend.utils.tts.genie_engine import GenieTTSEngine

logger = logging.getLogger(__name__)


def tts_worker_main(request_queue: Queue, response_queue: Queue, config: Dict[str, Any]):
    """TTS 工作进程入口点。"""
    try:
        asyncio.run(tts_worker_async(request_queue, response_queue, config))
    except Exception as e:
        logger.error(f"TTS 工作进程失败: {e}")
        traceback.print_exc()
        try:
            response_queue.put(("__ready__", False))
        except Exception:
            pass


async def tts_worker_async(request_queue: Queue, response_queue: Queue, config: Dict[str, Any]):
    """TTS 工作进程的异步主循环。"""
    logger.info("TTS Worker started")

    # 根据配置选择引擎：未启用时使用 Dummy，引擎启用时使用 Genie
    enabled = config.get("enabled", True)
    if not enabled:
        logger.info("TTS 已禁用，使用 DummyTTSEngine")
        engine: BaseTTSEngine = DummyTTSEngine()
    else:
        engine = GenieTTSEngine(config)

    # 初始化引擎
    if not await engine.initialize():
        logger.error("TTS 引擎初始化失败")
        try:
            response_queue.put(("__ready__", False))
        except Exception:
            pass
        return

    # 发送就绪信号
    logger.info("TTS Worker ready")
    response_queue.put(("__ready__", True))

    current_speech_id = None
    loop = asyncio.get_running_loop()

    try:
        while True:
            try:
                item = await loop.run_in_executor(None, request_queue.get)
            except Exception as e:
                logger.error(f"从队列获取数据时出错: {e}")
                break

            speech_id, text = item

            # 终止信号
            if speech_id is None and text is None:
                logger.info("收到终止信号")
                break

            # 中断检测
            if speech_id != current_speech_id:
                if current_speech_id is not None:
                    logger.info(f"中断语音 {current_speech_id} -> {speech_id}")
                current_speech_id = speech_id

            if text:
                await process_text_chunk(engine, text, response_queue)

    finally:
        await engine.shutdown()
        logger.info("TTS Worker 已停止")


async def process_text_chunk(engine: BaseTTSEngine, text: str, response_queue: Queue):
    """处理单个文本块并流式传输音频。"""
    try:
        async for audio_chunk in engine.synthesize_stream(text):
            response_queue.put(audio_chunk)
    except Exception as e:
        logger.error(f"合成失败: {e}")
