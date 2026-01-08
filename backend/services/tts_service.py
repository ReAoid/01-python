import asyncio
import logging
import time
import uuid
import queue
import traceback
import json
import re
from pathlib import Path
from multiprocessing import Process, Queue
from typing import Optional, Callable, Dict, Any, Union, Tuple

from backend.genie_server import ensure_genie_data
from backend.utils.tts.worker import tts_worker_main as external_tts_worker_main

logger = logging.getLogger(__name__)

"""
负责管理 TTS 子进程、处理文本请求队列、以及将生成的音频流回传给主进程。
"""


# ============================================================================
# TTS 服务管理器（主进程）
# ============================================================================


class TTSService:
    """
    TTS 服务管理器（主进程）。
    
    负责管理 TTS 子进程的生命周期，提供文本输入接口，并将接收到的音频流回调给上层应用。
    采用多进程架构以避免 TTS 合成（CPU密集/网络IO）阻塞主事件循环。
    
    Usage:
        tts = TTSService(config)
        await tts.start(on_audio_callback)
        await tts.push_text("你好，世界")
        # ...
        await tts.stop()
    """

    def __init__(self, config: Union[Dict, Any]):
        """
        初始化 TTS 服务。
        
        Args:
            config: 配置对象或字典。应包含 'tts' 和 'tts_characters' 等相关配置。
        """
        self.config = config
        self.tts_config = self._load_tts_config()

        # 多进程通信
        self.request_queue: Optional[Queue] = None
        self.response_queue: Optional[Queue] = None
        self.tts_process: Optional[Process] = None
        self.handler_task: Optional[asyncio.Task] = None

        # 缓存机制
        self.tts_ready = False
        self.pending_chunks = []
        self.cache_lock = asyncio.Lock()

        # 状态
        self.current_speech_id = str(uuid.uuid4())
        self.running = False
        # 音频数据回调函数
        self.on_audio: Optional[Callable[[Union[bytes, Tuple]], Any]] = None

    def _detect_language(self, text: str) -> str:
        """根据文本内容简单的语种检测"""
        if not text:
            return 'zh'
        if re.search(r'[\u4e00-\u9fff]', text):
            return 'zh'
        if re.search(r'[\u3040-\u309f\u30a0-\u30ff]', text):
            return 'jp'
        return 'en'

    def _load_tts_config(self) -> Dict[str, Any]:
        """
        解析并加载 TTS 配置。
        
        Returns:
            Dict[str, Any]: 扁平化的 TTS 配置字典，用于传给子进程。
        """
        
        # 默认值
        enabled = True
        host = '127.0.0.1'
        port = 8001
        character = 'feibi'
        genie_data_dir = None
        
        # 1. 从配置对象读取基础信息
        if isinstance(self.config, dict):
            # 兼容字典配置 (测试或简单调用)
            tts = self.config.get('tts', self.config)
            server = tts.get('server', {}) if 'server' in tts else tts
            
            enabled = tts.get('enabled', enabled)
            character = tts.get('active_character', character)
            genie_data_dir = tts.get('genie_data_dir', genie_data_dir)
            
            # 尝试从不同位置获取 host/port
            host = server.get('host', tts.get('server_host', host))
            port = server.get('port', tts.get('server_port', port))
        else:
            # Pydantic Settings 对象
            t = self.config.tts
            enabled = t.enabled
            host = t.server.host
            port = t.server.port
            character = t.active_character
            genie_data_dir = t.genie_data_dir

        # 2. 确定数据目录路径
        # 尝试查找有效的 TTS 目录 (使用项目目录)
        from backend.config.manager import get_config_manager
        tts_base_dir = get_config_manager().get_tts_base_dir()
        
        # 确定目标目录（但还未确认存在）
        if genie_data_dir:
            target_dir = str(genie_data_dir)
        else:
            # 否则使用项目源码中的 TTS 目录下的 GenieData
            target_dir = str(tts_base_dir / "GenieData")

        # 确保数据目录存在（并处理环境变量和下载）
        try:
            # 这一步会下载模型如果不存在
            genie_data_path = ensure_genie_data(target_dir)
            genie_data_dir = str(genie_data_path)
        except Exception as e:
            logger.warning(f"自动检查/下载模型失败: {e}")
            genie_data_dir = target_dir

        # 3. 根据 character 查找文件配置
        # 路径结构: {genie_data_dir}/CharacterModels/v2ProPlus/{character}/
        try:
            base_dir = Path(genie_data_dir) # 使用 genie_data_dir 作为基准
            character_dir = base_dir / "CharacterModels" / "v2ProPlus" / character
            prompt_config_path = character_dir / "prompt_wav.json"
            
            # 默认值
            language = 'zh'
            reference_audio_path = None
            reference_audio_text = None
            model_dir = str(character_dir / "tts_models")

            if prompt_config_path.exists():
                try:
                    with open(prompt_config_path, 'r', encoding='utf-8') as f:
                        prompt_data = json.load(f)
                        # 假设使用 Normal 配置
                        normal_config = prompt_data.get("Normal", {})
                        wav_name = normal_config.get("wav")
                        reference_audio_text = normal_config.get("text")
                        
                        if wav_name:
                            reference_audio_path = str(character_dir / "prompt_wav" / wav_name)
                        
                        # 自动推断语言
                        if reference_audio_text:
                            language = self._detect_language(reference_audio_text)
                except Exception as e:
                    logger.error(f"读取角色配置文件失败 {prompt_config_path}: {e}")
            else:
                logger.warning(f"找不到角色配置文件: {prompt_config_path}")

            return {
                'enabled': enabled,
                'host': host,
                'port': port,
                'character': character,
                'language': language,
                'model_dir': model_dir,
                'reference_audio_path': reference_audio_path,
                'reference_audio_text': reference_audio_text,
            }
            
        except Exception as e:
            logger.error(f"加载 TTS 角色配置过程发生未知错误: {e}")
            return {
                'enabled': enabled,
                'host': host,
                'port': port,
                'character': character,
                'language': 'zh',
                'model_dir': None,
                'reference_audio_path': None,
                'reference_audio_text': None,
            }

    async def start(self, on_audio: Callable[[Union[bytes, Tuple]], Any]):
        """
        启动 TTS 服务（子进程）。
        
        Args:
            on_audio: 音频数据回调函数。签名应为 async def on_audio(data: bytes | tuple)。
        """
        self.on_audio = on_audio
        self.running = True

        start_time = time.time()
        logger.info("🎤 正在启动 TTS 服务...")

        # 初始化队列
        # 注意：在某些环境中（如 macOS 默认 spawn 模式），我们需要将队列传递给进程
        self.request_queue = Queue()
        self.response_queue = Queue()

        # 启动子进程
        self.tts_process = Process(
            target=external_tts_worker_main,
            args=(self.request_queue, self.response_queue, self.tts_config)
        )
        self.tts_process.daemon = True
        self.tts_process.start()

        # 等待就绪信号（非阻塞）
        try:
            # 增加超时时间以适应首次模型加载或慢速机器
            ready = await self._wait_for_ready_signal(timeout=30.0)
            if not ready:
                logger.error("❌ TTS 进程初始化失败 (超时或错误)")
                # 如果失败，重置运行状态
                self.running = False
                return False
        except Exception as e:
            logger.error(f"等待 TTS 就绪时出错: {e}")
            self.running = False
            return False

        logger.success(f"✅ TTS 服务已启动 (耗时 {time.time() - start_time:.2f}秒)")

        # 启动响应处理器
        self.handler_task = asyncio.create_task(self._response_handler())

        # 标记为就绪并刷新任何待处理的块（如果在启动期间有累积的话）
        async with self.cache_lock:
            self.tts_ready = True
        await self._flush_pending_chunks()

        return True

    async def stop(self):
        """停止 TTS 服务并清理资源。"""
        self.running = False
        logger.info("正在停止 TTS 服务...")

        # 1. 取消处理器
        if self.handler_task and not self.handler_task.done():
            self.handler_task.cancel()
            try:
                await self.handler_task
            except asyncio.CancelledError:
                pass

        # 2. 终止进程
        if self.tts_process and self.tts_process.is_alive():
            try:
                # 发送终止信号
                if self.request_queue:
                    self.request_queue.put((None, None))

                self.tts_process.join(timeout=1.0)
                if self.tts_process.is_alive():
                    self.tts_process.terminate()
            except Exception as e:
                logger.error(f"停止 TTS 进程时出错: {e}")

        self.tts_process = None
        self.request_queue = None
        self.response_queue = None
        self.tts_ready = False
        logger.info("TTS 服务已停止")

    async def push_text(self, text: str):
        """
        推送文本到 TTS 服务进行合成。
        
        如果是首次调用或 TTS 未就绪，文本会被缓存并在一起绪后发送。
        
        Args:
            text: 要合成的文本字符串。
        """
        if not text:
            return

        async with self.cache_lock:
            if self.tts_ready and self.request_queue:
                # TTS 已就绪，直接发送
                try:
                    self.request_queue.put((self.current_speech_id, text))
                except Exception as e:
                    logger.error(f"推送文本到 TTS 失败: {e}")
            else:
                # 缓冲文本
                self.pending_chunks.append((self.current_speech_id, text))
                if len(self.pending_chunks) == 1:
                    logger.info("TTS 未就绪，正在缓冲文本...")

    async def flush(self):
        """
        等待队列处理（当前架构下主要作为占位符）。
        """
        pass

    async def clear_queue(self):
        """
        清空待处理的文本队列（通过中断实现）。
        """
        await self.interrupt()

    async def interrupt(self):
        """
        中断当前语音播放。
        
        机制：
        1. 生成新的 speech_id。
        2. 清除本地缓存 (pending_chunks)。
        3. 清空输入队列 (request_queue) - 丢弃待处理的请求。
        4. 清空输出队列 (response_queue) - 丢弃已生成但未播放的音频。
        5. 发送新 ID 信号给 Worker（Worker 检测到 ID 变化会丢弃旧任务）。
        """
        new_id = str(uuid.uuid4())
        logger.info(f"中断语音 {self.current_speech_id} -> {new_id}")

        # 1. 清除本地缓存
        async with self.cache_lock:
            self.pending_chunks.clear()

        # 2. 清空输入队列 (request_queue)
        if self.request_queue:
            while not self.request_queue.empty():
                try:
                    self.request_queue.get_nowait()
                except queue.Empty:
                    break

        # 3. 清空输出队列 (response_queue) - 关键!
        if self.response_queue:
            while not self.response_queue.empty():
                try:
                    self.response_queue.get_nowait()
                except queue.Empty:
                    break

        # 4. 更新 speech ID（这将使下次 push_text 使用新 ID）
        self.current_speech_id = new_id

        # 5. 发送中断信号给 worker
        if self.request_queue:
            self.request_queue.put((new_id, ""))

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
                        # Put back if not ready signal (unlikely during startup)
                        self.response_queue.put(msg)
                except:
                    pass
            await asyncio.sleep(0.05)
        return False

    async def _response_handler(self):
        """
        后台任务：处理来自 Worker 的响应队列。
        """
        logger.info("TTS 响应处理器已启动")

        while self.running:
            try:
                if self.response_queue and not self.response_queue.empty():
                    try:
                        data = self.response_queue.get_nowait()

                        # 过滤信号
                        if isinstance(data, tuple) and data[0] == "__ready__":
                            continue

                        # 音频数据
                        if self.on_audio:
                            await self.on_audio(data)

                    except queue.Empty:
                        pass
                    except Exception as e:
                        logger.error(f"响应处理器出错: {e}")

                await asyncio.sleep(0.01)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"响应处理器循环出错: {e}")
                await asyncio.sleep(1)

    async def _flush_pending_chunks(self):
        """将缓存的文本块发送给 Worker。"""
        async with self.cache_lock:
            if not self.pending_chunks:
                return

            logger.info(f"正在刷新 {len(self.pending_chunks)} 个缓冲块")
            if self.request_queue:
                for speech_id, text in self.pending_chunks:
                    try:
                        self.request_queue.put((speech_id, text))
                    except Exception as e:
                        logger.error(f"刷新块时出错: {e}")
            self.pending_chunks.clear()
