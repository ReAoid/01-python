"""ASR 服务管理器

负责管理 ASR 子进程、处理音频请求队列、以及将识别结果回传给主进程。
采用多进程架构以避免 ASR 识别（CPU密集）阻塞主事件循环。
"""

import logging
import asyncio
import time
import queue
from multiprocessing import Process, Queue
from typing import Optional, Callable, Any, Union, Tuple

from backend.utils.asr.worker import asr_worker_main

logger = logging.getLogger(__name__)


class ASRService:
    """
    ASR 服务管理器（主进程）。
    
    负责管理 ASR 子进程的生命周期，提供音频输入接口，并将接收到的转录结果和 VAD 事件回调给上层应用。
    采用多进程架构以避免 ASR 识别（CPU密集/IO密集）阻塞主事件循环。
    
    Usage:
        asr = ASRService(settings)
        await asr.start(on_transcript_callback, on_vad_trigger_callback)
        await asr.push_audio_data(audio_bytes)
        # ...
        await asr.stop()
    """
    
    def __init__(self, settings: Any):
        """
        初始化 ASR 服务。
        
        Args:
            settings: Settings 对象（包含 asr 配置）
        """
        self.settings = settings
        
        # 多进程通信
        self.request_queue: Optional[Queue] = None
        self.response_queue: Optional[Queue] = None
        self.asr_process: Optional[Process] = None
        self.handler_task: Optional[asyncio.Task] = None
        
        # 状态
        self.running = False
        self.asr_ready = False
        
        # 回调函数
        self.on_transcript: Optional[Callable] = None
        self.on_vad_trigger: Optional[Callable] = None
        
        # 构建 worker 配置
        self.asr_config = self._build_worker_config()

    def _build_worker_config(self) -> dict:
        """
        构建 ASR Worker 配置字典。
        
        从 settings.asr 提取配置，构建用于子进程的配置字典。
        """
        # 从 settings.asr 读取配置（如果存在）
        asr_settings = self.settings.asr if self.settings else None
        
        # 引擎类型
        engine = "dummy"
        if asr_settings and hasattr(asr_settings, "engine"):
            engine = asr_settings.engine
        
        # 基本配置
        model_path = None
        if asr_settings and hasattr(asr_settings, "model_path"):
            model_path = asr_settings.model_path
        
        device = "cpu"
        if asr_settings and hasattr(asr_settings, "device"):
            device = asr_settings.device
        
        language = "zh"
        if asr_settings and hasattr(asr_settings, "language"):
            language = asr_settings.language
        
        # 从 settings.asr.audio 中读取音频配置
        if asr_settings and hasattr(asr_settings, "audio"):
            audio_obj = asr_settings.audio
            if hasattr(audio_obj, "__dict__"):
                audio_config = {
                    "sample_rate": getattr(audio_obj, "sample_rate", None),
                    "channels": getattr(audio_obj, "channels", None),
                    "sample_width": getattr(audio_obj, "sample_width", None),
                }
            elif isinstance(audio_obj, dict):
                audio_config = {
                    "sample_rate": audio_obj.get("sample_rate"),
                    "channels": audio_obj.get("channels"),
                    "sample_width": audio_obj.get("sample_width"),
                }
            else:
                audio_config = {}
        else:
            audio_config = {}
        
        # 如果 settings 有更详细的配置，合并进来
        if asr_settings:
            if hasattr(asr_settings, "vad"):
                vad_obj = asr_settings.vad
                if hasattr(vad_obj, "__dict__"):
                    vad_config = vars(vad_obj)
                elif isinstance(vad_obj, dict):
                    vad_config = vad_obj
                else:
                    vad_config = {}
            else:
                vad_config = {}
            
            if hasattr(asr_settings, "preprocessing"):
                prep_obj = asr_settings.preprocessing
                if hasattr(prep_obj, "__dict__"):
                    preprocessing_config = vars(prep_obj)
                elif isinstance(prep_obj, dict):
                    preprocessing_config = prep_obj
                else:
                    preprocessing_config = {}
            else:
                preprocessing_config = {}
        else:
            vad_config = {}
            preprocessing_config = {}
        
        # 构建配置字典
        config_dict = {
            "engine": engine,
            "model_path": model_path,
            "device": device,
            "language": language,
            "vad": vad_config,
            "audio": audio_config,
            "preprocessing": preprocessing_config,
        }
        
        return config_dict
    
    async def start(self, on_transcript: Callable, on_vad_trigger: Callable):
        """
        启动 ASR 服务（子进程）。
        
        Args:
            on_transcript: 转录结果回调函数 async def on_transcript(text: str)
            on_vad_trigger: VAD 触发回调函数 async def on_vad_trigger()
        """
        self.on_transcript = on_transcript
        self.on_vad_trigger = on_vad_trigger
        self.running = True
        
        start_time = time.time()
        logger.info("🎙️ 正在启动 ASR 服务...")
        
        # 初始化队列
        self.request_queue = Queue()
        self.response_queue = Queue()
        
        # 启动子进程
        self.asr_process = Process(
            target=asr_worker_main,
            args=(self.request_queue, self.response_queue, self.asr_config)
        )
        self.asr_process.daemon = True
        self.asr_process.start()
        
        # 等待就绪信号（非阻塞）
        try:
            ready = await self._wait_for_ready_signal(timeout=30.0)
            if not ready:
                logger.error("❌ ASR 进程初始化失败 (超时或错误)")
                self.running = False
                return False
        except Exception as e:
            logger.error(f"等待 ASR 就绪时出错: {e}")
            self.running = False
            return False
        
        logger.success(f"✅ ASR 服务已启动 (耗时 {time.time() - start_time:.2f}秒)")
        
        # 启动响应处理器
        self.handler_task = asyncio.create_task(self._response_handler())
        self.asr_ready = True
        
        return True

    async def stop(self):
        """停止 ASR 服务并清理资源。"""
        self.running = False
        logger.info("正在停止 ASR 服务...")
        
        # 1. 取消处理器
        if self.handler_task and not self.handler_task.done():
            self.handler_task.cancel()
            try:
                await self.handler_task
            except asyncio.CancelledError:
                pass
        
        # 2. 终止进程
        if self.asr_process and self.asr_process.is_alive():
            try:
                # 发送终止信号
                if self.request_queue:
                    self.request_queue.put(("__stop__", None))
                
                self.asr_process.join(timeout=1.0)
                if self.asr_process.is_alive():
                    self.asr_process.terminate()
            except Exception as e:
                logger.error(f"停止 ASR 进程时出错: {e}")
        
        self.asr_process = None
        self.request_queue = None
        self.response_queue = None
        self.asr_ready = False
        logger.info("ASR 服务已停止")
    
    async def push_audio_data(self, audio_data: bytes):
        """
        推送音频数据到 ASR 服务进行识别。
        
        Args:
            audio_data: PCM 音频数据（bytes）
                格式要求：
                - 采样率: 16000 Hz
                - 位深: 16-bit (2 bytes per sample)
                - 声道: 单声道 (Mono)
                - 字节序: Little-endian
        """
        if not self.running or not self.asr_ready:
            return
        
        if not audio_data:
            return
        
        try:
            # 发送音频数据到子进程
            if self.request_queue:
                self.request_queue.put(("audio", audio_data))
        except Exception as e:
            logger.error(f"推送音频数据到 ASR 失败: {e}")
    
    async def clear_buffer(self):
        """清空音频缓冲区（用于打断场景）"""
        if self.request_queue:
            try:
                # 发送清空缓冲信号
                self.request_queue.put(("__clear__", None))
                logger.debug("ASR buffer clear signal sent")
            except Exception as e:
                logger.error(f"发送清空缓冲信号失败: {e}")
    
    async def _wait_for_ready_signal(self, timeout: float) -> bool:
        """等待 Worker 发送准备就绪信号。"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.response_queue and not self.response_queue.empty():
                try:
                    msg = self.response_queue.get_nowait()
                    if isinstance(msg, tuple) and len(msg) == 2 and msg[0] == "__ready__":
                        return msg[1]
                    else:
                        # Put back if not ready signal
                        self.response_queue.put(msg)
                except:
                    pass
            await asyncio.sleep(0.05)
        return False
    
    async def _response_handler(self):
        """
        后台任务：处理来自 Worker 的响应队列。
        """
        logger.info("ASR 响应处理器已启动")
        
        while self.running:
            try:
                if self.response_queue and not self.response_queue.empty():
                    try:
                        msg = self.response_queue.get_nowait()
                        
                        # 过滤就绪信号
                        if isinstance(msg, tuple) and msg[0] == "__ready__":
                            continue
                        
                        # 处理不同类型的消息
                        if isinstance(msg, tuple) and len(msg) == 2:
                            msg_type, data = msg
                            
                            # 转录结果
                            if msg_type == "transcript" and self.on_transcript:
                                await self.on_transcript(data)
                            
                            # VAD 触发
                            elif msg_type == "vad_trigger" and self.on_vad_trigger:
                                await self.on_vad_trigger()
                    
                    except queue.Empty:
                        pass
                
                await asyncio.sleep(0.01)  # 避免 CPU 100%
            
            except Exception as e:
                logger.error(f"ASR 响应处理器错误: {e}", exc_info=True)
        
        logger.info("ASR 响应处理器已停止")
