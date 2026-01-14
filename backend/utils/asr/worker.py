"""
ASR Worker 模块

从 asr_service 中抽取出的子进程逻辑，负责在独立进程中调用具体 ASR 引擎进行实时音频识别。
"""

import asyncio
import logging
import traceback
from multiprocessing import Queue
from typing import Dict, Any, Optional

from backend.utils.asr.base_engine import BaseASREngine
from backend.utils.asr.dummy_engine import DummyASREngine
from backend.utils.asr.funasr_automodel_engine import FunASRAutoModelEngine

logger = logging.getLogger(__name__)


def asr_worker_main(request_queue: Queue, response_queue: Queue, config: Dict[str, Any]):
    """ASR 工作进程入口点。"""
    try:
        asyncio.run(asr_worker_async(request_queue, response_queue, config))
    except Exception as e:
        logger.error(f"ASR 工作进程失败: {e}")
        traceback.print_exc()
        try:
            response_queue.put(("__ready__", False))
        except Exception:
            pass


async def asr_worker_async(request_queue: Queue, response_queue: Queue, config: Dict[str, Any]):
    """ASR 工作进程的异步主循环。"""
    logger.info("ASR Worker started")
    
    # 根据配置选择引擎
    engine_type = config.get("engine", "dummy")
    enabled = config.get("enabled", True)
    
    if enabled and engine_type == "funasr_automodel":
        logger.info("使用 FunASRAutoModelEngine")
        engine: BaseASREngine = FunASRAutoModelEngine(config)
    else:
        logger.info("使用 DummyASREngine (default)")
        engine = DummyASREngine(config)

    # 初始化引擎
    if not await engine.initialize():
        logger.error("ASR 引擎初始化失败")
        try:
            response_queue.put(("__ready__", False))
        except Exception:
            pass
        return

    # 发送就绪信号
    logger.info("ASR Worker ready")
    response_queue.put(("__ready__", True))

    loop = asyncio.get_running_loop()

    try:
        while True:
            try:
                # 从队列获取音频数据
                item = await loop.run_in_executor(None, request_queue.get)
            except Exception as e:
                logger.error(f"从队列获取数据时出错: {e}")
                break

            # 解析消息
            if isinstance(item, tuple) and len(item) == 2:
                msg_type, data = item
                
                # 终止信号
                if msg_type == "__stop__":
                    logger.info("收到终止信号")
                    break
                
                # 清空缓冲信号
                elif msg_type == "__clear__":
                    logger.debug("清空 ASR 缓冲区")
                    await engine.clear_buffer()
                
                # 音频数据
                elif msg_type == "audio":
                    await process_audio_chunk(engine, data, response_queue)
            
            else:
                logger.warning(f"收到未知消息格式: {type(item)}")

    finally:
        await engine.shutdown()
        logger.info("ASR Worker 已停止")


async def process_audio_chunk(engine: BaseASREngine, audio_data: bytes, response_queue: Queue):
    """
    处理单个音频块并返回识别结果。
    
    Args:
        engine: ASR 引擎实例
        audio_data: PCM 音频数据
        response_queue: 响应队列
    """
    try:
        # 1. 进行语音识别
        text = await engine.process_audio(audio_data)
        if text:
            # 发送转录结果
            response_queue.put(("transcript", text))
        
        # 2. 检测 VAD（用于打断）
        is_speech = await engine.detect_vad(audio_data)
        if is_speech:
            # 发送 VAD 触发事件
            response_queue.put(("vad_trigger", True))
    
    except Exception as e:
        logger.error(f"处理音频时发生异常: {e}", exc_info=True)
