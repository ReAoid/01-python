import asyncio
import logging
import time
import json
from enum import Enum
from typing import List, Dict, Optional
import re

from fastapi import WebSocket, WebSocketDisconnect

# 引入项目现有组件
from backend.config import settings
from backend.config.prompts import build_personalized_system_prompt

# 引入服务组件
from backend.services.asr_service import ASRService
from backend.services.tts_service import TTSService
from backend.utils.llm.text_llm_client import TextLLMClient
from backend.core.event_bus import event_bus, Event, EventType
from backend.utils.memory.memory_manager import MemoryManager, generate_session_id
from backend.services.llm_service import get_llm

logger = logging.getLogger(__name__)


class InputMode(Enum):
    """
    输入模式枚举。
    定义系统接收用户输入的方式。
    """
    TEXT = "text"  # 文本输入
    AUDIO = "audio"  # 普通音频输入
    REALTIME_AUDIO = "realtime_audio"  # 实时音频输入
    VISION = "vision"  # 视觉系统输入


class OutputMode(Enum):
    """
    输出模式枚举。
    定义系统向用户返回响应的方式。
    """
    TEXT_ONLY = "text_only"  # 仅输出文本
    TEXT_AND_AUDIO = "text_audio"  # 输出文本和音频 (TTS)


# --- 核心 Session Manager ---

class SessionManager:
    """
    会话管理器核心类。
    负责管理 ASR、LLM、TTS 三大组件的协同工作,实现无缝的双 Session 热切换机制。
    
    主要功能:
    - 管理输入输出管道 (ASR/TTS)
    - 实现双 Session 架构,支持热切换
    - 处理用户输入并生成响应
    - 管理增量记忆缓存,防止切换时失忆
    """
    
    def __init__(self, message_queue: asyncio.Queue, memory_manager: MemoryManager = None):
        """
        初始化会话管理器。
        
        Args:
            message_queue: 用于与 Agent/Monitor 通信的异步队列
            memory_manager: 共享的记忆管理器实例，如果为 None 则创建新的
        """
        # 加载配置
        self.config = settings
        # 用于与 Agent/Monitor 通信
        self.queue = message_queue

        # --- 管道组件 ---
        # ASRService 从 settings 中构建自身配置
        self.asr = ASRService(self.config)
        # TTSService 使用 settings 对象
        self.tts = TTSService(self.config)

        # --- 记忆管理 ---
        if memory_manager:
            self.memory_manager = memory_manager
            # 如果复用了 memory_manager，我们可以复用它的 llm 或者不持有 llm_memory_service
            # 如果 memory_manager.llm 是 Llm 类型，我们引用它，否则新建（通常是复用）
            self.llm_memory_service = getattr(memory_manager, 'llm', None) or get_llm()
        else:
            self.llm_memory_service = get_llm()
            self.memory_manager = MemoryManager(llm=self.llm_memory_service)

        # --- 双 Session 架构 (实现热切换) ---
        self.current_llm: Optional[TextLLMClient] = None  # 当前服务中的 LLM
        self.pending_llm: Optional[TextLLMClient] = None  # 后台预热中的 LLM

        # --- 热切换关键状态 ---
        self.session_start_time = 0  # 会话开始时间
        self.is_swapping = False  # 是否正在交换会话
        self.renew_threshold = 60  # 1分钟
        self.conversation_count = 0  # 对话条数计数器
        self.conversation_threshold = 10  # 对话条数阈值

        # --- [关键] 增量记忆缓存 ---
        # 用于记录在"后台预热期间"产生的新对话，防止切换后失忆
        self.incremental_cache: List[Dict] = []
        self.is_preparing_renew = False  # 是否正在预热新的会话

        # --- 状态 ---
        self.is_active = False
        self.input_mode = InputMode.TEXT
        self.output_mode = OutputMode.TEXT_ONLY
        self.websocket: Optional[WebSocket] = None

        # --- 通信控制组件 ---
        self.input_queue = []          # 智能缓存队列 (用于暂存未就绪时的输入)
        self.lock = asyncio.Lock()     # 异步锁 (保护共享状态)
        self.is_ready = False          # 系统就绪标志

        # --- 任务管理 ---
        self.consumer_task: Optional[asyncio.Task] = None
        self.last_user_input: Optional[str] = None  # 记录最后的用户输入用于事件广播
        
        # 订阅系统通知
        event_bus.subscribe(EventType.TASK_COMPLETED, self._on_task_completed)
        event_bus.subscribe(EventType.MEMORY_UPDATED, self._on_memory_updated)
        event_bus.subscribe(EventType.LOG_ENTRY, self._on_log_entry)

    async def _on_task_completed(self, event: Event):
        """处理任务完成通知。"""
        if not self.websocket: return
        
        result = event.data.get("result")
        if result:
            # 作为特殊系统消息或纯文本发送
            await self._send_text_to_frontend(f"【系统任务完成】 {result}")

    async def _on_memory_updated(self, event: Event):
        """处理自我意识更新。"""
        if not self.websocket: return
        
        content = event.data.get("content")
        source = event.data.get("source")
        
        if source == "self_awareness" and content:
            await self._send_text_to_frontend(f"【AI 自我思考】 {content}")

    async def _on_log_entry(self, event: Event):
        """
        处理日志条目，转发到前端 WebSocket。
        只在 WebSocket 连接正常时推送。
        """
        if not self.websocket:
            return
        
        try:
            # 直接转发日志数据
            await self.websocket.send_text(json.dumps({
                'type': 'log_entry',
                'data': event.data
            }))
        except Exception as e:
            # 静默失败，不影响主流程
            logger.debug(f"Failed to send log to frontend: {e}")

    # =========================================================================
    # 1. 生命周期与管道启动
    # =========================================================================

    async def start(self, websocket: WebSocket, input_mode: InputMode = InputMode.TEXT, output_mode: OutputMode = OutputMode.TEXT_ONLY):
        """
        系统启动入口,并行初始化所有组件。
        
        Args:
            websocket: WebSocket 连接对象,用于与前端通信
            input_mode: 输入方式 (AUDIO/TEXT),默认为文本输入
            output_mode: 输出方式 (TEXT_ONLY/TEXT_AND_AUDIO),默认为仅文本输出
        """
        self.websocket = websocket
        self.input_mode = input_mode
        self.output_mode = output_mode
        self.session_start_time = time.time()

        logger.info("🚀 Starting system components in parallel...")
        
        # 1. 启动监听循环 (非阻塞，作为后台任务运行)
        # 必须先启动监听，才能接收前端的消息
        listen_task = asyncio.create_task(self._listen_loop())

        try:
            # 2. 并行初始化内部组件 (LLM, TTS, ASR)
            # 加锁，表示正在初始化，暂不能处理业务数据
            async with self.lock:
                self.is_ready = False
                await self._init_components(input_mode, output_mode)
                self.is_ready = True
            
            # 3. 初始化完成后，处理积压的数据 (Smart Buffering)
            await self._process_queued_data()
            
            self.is_active = True
            
            # 4. 等待监听循环结束 (通常是连接断开时)
            await listen_task

        except asyncio.CancelledError:
            logger.info("Session task cancelled")
        except Exception as e:
            logger.error(f"Session error: {e}", exc_info=True)
        finally:
            await self.stop()
            
    async def _init_components(self, input_mode: InputMode, output_mode: OutputMode):
        """
        初始化 LLM, TTS, ASR 等组件
        """
        start_time = time.time()
        tasks = []

        # 1. 启动 TTS (仅在需要音频输出时启动)
        if output_mode == OutputMode.TEXT_AND_AUDIO:
            tasks.append(self.tts.start(on_audio=self._send_audio_to_frontend))

        # 2. 启动 ASR (仅在语音输入模式下启动)
        if input_mode in (InputMode.AUDIO, InputMode.REALTIME_AUDIO):
            tasks.append(self.asr.start(
                on_transcript=self._handle_user_input,  # ASR 转录结果 -> LLM
                on_vad_trigger=self._handle_interrupt  # 用户打断 -> 停止生成
            ))

        # 3. 启动核心 LLM (冷启动)
        async def start_llm():
            self.current_llm = await self._create_llm_session(is_renew=False)

        tasks.append(start_llm())

        # 并行执行所有启动任务
        await asyncio.gather(*tasks)
        
        # 如果需要音频输出但 TTS 未成功就绪，通知前端
        if output_mode == OutputMode.TEXT_AND_AUDIO and not self.tts.tts_ready:
            error_msg = "TTS 服务启动失败，将仅以文本形式回复"
            await self._send_text_to_frontend(f"【系统提示】{error_msg}")
            await self._send_service_error("tts", error_msg)
        
        # 如果需要语音输入但 ASR 未成功就绪，通知前端
        if input_mode in (InputMode.AUDIO, InputMode.REALTIME_AUDIO) and not self.asr.asr_ready:
            error_msg = "ASR 服务启动失败，请检查服务状态"
            await self._send_text_to_frontend(f"【系统提示】{error_msg}")
            await self._send_service_error("asr", error_msg)
        
        logger.info(
            f"系统组件初始化完成 (耗时 {time.time() - start_time:.2f}秒, 输入: {input_mode.value}, 输出: {output_mode.value})")

    async def stop(self):
        """
        系统停止,清理所有资源。
        取消正在运行的任务,关闭所有服务连接。
        """
        self.is_active = False
        if self.consumer_task and not self.consumer_task.done():
            self.consumer_task.cancel()
        if self.current_llm: await self.current_llm.close()
        if self.pending_llm: await self.pending_llm.close()
        await self.asr.stop()
        await self.tts.stop()

    # =========================================================================
    # 2. WebSocket 监听与分发
    # =========================================================================

    async def _listen_loop(self):
        """
        [接收端] 无限循环，监听 WebSocket 消息
        """
        try:
            while True:
                # 1. 接收消息 (Text Frame 承载 JSON, Binary Frame 承载音频)
                if not self.websocket:
                    break
                    
                # 修改：使用 receive() 同时接收文本和二进制
                message = await self.websocket.receive()
                
                if message["type"] == "websocket.receive":
                    if "text" in message:
                        # 文本消息 (JSON)
                        data = message["text"]
                        if not data: continue
                        
                        try:
                            msg_obj = json.loads(data)
                            # 异步分发
                            asyncio.create_task(self._dispatch_action(msg_obj))
                        except json.JSONDecodeError:
                            logger.warning("Received invalid JSON")
                            continue
                            
                    elif "bytes" in message:
                        # 二进制消息 (音频)
                        data = message["bytes"]
                        if not data: continue
                        
                        # 异步处理音频输入
                        asyncio.create_task(self._process_audio_input(data))

                elif message["type"] == "websocket.disconnect":
                    break

        except WebSocketDisconnect:
            logger.info("WebSocket disconnected")
        except Exception as e:
            logger.error(f"Error in listen loop: {e}")
        finally:
            self.is_active = False

    async def _dispatch_action(self, message: dict):
        """
        [分发器] 根据 type 路由消息
        """
        action = message.get("type")
        if not action:
            logger.warning("Message missing 'type' field, ignoring")
            return
        
        if action == "stream_data":
            # 处理流式数据 (核心业务)
            await self._handle_stream_data(message)

        elif action == "user_text":
             # 协议定义的文本消息
            content = message.get("content")
            if content:
                await self._handle_user_input(content)
            
        elif action == "interrupt":
            # 处理打断
            await self._handle_interrupt()
            
        elif action == "config":
            # 处理配置更新
            data = message.get("data", {})
            if "input_mode" in data:
                try:
                    new_input_mode = InputMode(data["input_mode"])
                    
                    # 处理ASR持续录音模式的启动和停止
                    if new_input_mode == InputMode.REALTIME_AUDIO and self.input_mode != InputMode.REALTIME_AUDIO:
                        # 切换到实时音频模式，启动ASR服务
                        if not self.asr.running:
                            logger.info("Switching to Realtime Audio mode: Starting ASR service...")
                            success = await self.asr.start(
                                on_transcript=self._handle_asr_transcript,
                                on_vad_trigger=self._handle_vad_trigger
                            )
                            if success:
                                logger.info("✅ ASR 服务启动成功（持续录音模式）")
                            else:
                                error_msg = "ASR 服务启动失败，请检查服务状态"
                                await self._send_text_to_frontend(f"【系统提示】{error_msg}")
                                await self._send_service_error("asr", error_msg)
                                # 不切换到实时音频模式
                                return
                    elif new_input_mode != InputMode.REALTIME_AUDIO and self.input_mode == InputMode.REALTIME_AUDIO:
                        # 从实时音频模式切换出去，停止ASR服务
                        if self.asr.running:
                            logger.info("Leaving Realtime Audio mode: Stopping ASR service...")
                            await self.asr.stop()
                            logger.info("✅ ASR 服务已停止")
                    
                    self.input_mode = new_input_mode
                except ValueError:
                    pass
            if "output_mode" in data:
                try:
                    new_mode = OutputMode(data["output_mode"])
                    
                    # 关键修复：如果切换到含音频模式且 TTS 未运行，则立即启动
                    if new_mode == OutputMode.TEXT_AND_AUDIO and not self.tts.running:
                        logger.info("Switching to Audio mode: Lazy starting TTS service...")
                        # 启动 TTS，传入音频回调
                        success = await self.tts.start(on_audio=self._send_audio_to_frontend)
                        if success:
                            logger.info("✅ TTS 服务懒启动成功")
                        else:
                            error_msg = "TTS 服务启动失败，请检查服务状态"
                            await self._send_text_to_frontend(f"【系统提示】{error_msg}")
                            await self._send_service_error("tts", error_msg)
                            # 不切换到音频模式
                            return

                    self.output_mode = new_mode
                except ValueError:
                    pass
            
        elif action == "ping":
            # 心跳回应
            if self.websocket:
                try:
                    await self.websocket.send_text(json.dumps({"type": "pong"}))
                except Exception:
                    pass
        
        elif action == "hot_reload":
            # 处理主动热更新请求
            await self._handle_hot_reload()

    async def _handle_stream_data(self, message: dict):
        """
        处理输入数据，具备未就绪缓存功能
        """
        async with self.lock:
            # 如果系统还没准备好 (例如 LLM 正在连接中)，将数据存入缓存
            if not self.is_ready:
                self.input_queue.append(message)
                logger.info("System not ready, buffering data...")
                return

        # 系统已就绪，直接处理
        await self._process_single_message(message)

    async def _process_queued_data(self):
        """
        处理缓存队列中的积压数据
        """
        if self.input_queue:
            logger.info(f"Processing {len(self.input_queue)} buffered messages...")
            while self.input_queue:
                msg = self.input_queue.pop(0)
                await self._process_single_message(msg)

    async def _process_single_message(self, message: dict):
        """
        实际的业务逻辑处理
        """
        input_type = message.get("input_type")
        data = message.get("data")

        if input_type == "text":
            # 路由到现有的文本处理函数
            await self._handle_user_input(data)
            
        elif input_type == "audio":
            # 路由到 ASR 服务，仅支持 PCM 二进制数据
            await self._process_audio_input(data)

    async def _process_audio_input(self, data: bytes):
        """
        处理音频输入数据（仅支持 PCM 二进制格式）
        
        Args:
            data: PCM 音频数据 (bytes)
                格式要求：
                - 采样率: 16000 Hz
                - 位深: 16-bit (2 bytes per sample)
                - 声道: 单声道 (Mono)
                - 字节序: Little-endian
        """
        if not isinstance(data, bytes):
            logger.error(f"Invalid audio data type: {type(data)}, expected bytes")
            return
        
        if not data:
            logger.warning("Received empty audio data")
            return
        
        try:
            logger.debug(f"Received PCM audio data: {len(data)} bytes")
            # 推送音频数据到 ASR 服务
            await self.asr.push_audio_data(data)
        except Exception as e:
            logger.error(f"Error processing audio input: {e}", exc_info=True)
    
    async def _handle_asr_transcript(self, text: str):
        """
        处理ASR转录结果的回调函数
        
        当ASR服务通过VAD检测到完整的语音片段并转录完成后，会调用此函数。
        
        Args:
            text: ASR识别出的文本
        """
        if not text or not text.strip():
            return
        
        logger.info(f"📝 ASR转录结果: {text}")
        
        # 1. 先将ASR识别的文字发送到前端，显示为用户消息
        await self._send_user_message_to_frontend(text)
        
        # 2. 将转录的文本作为用户输入处理
        await self._handle_user_input(text)
    
    async def _handle_vad_trigger(self):
        """
        处理VAD触发事件的回调函数
        
        当ASR服务检测到用户开始说话时（VAD触发），会调用此函数。
        可以用于打断AI的语音输出。
        """
        logger.debug("🎤 VAD触发：检测到用户语音")
        
        # 如果TTS正在运行，打断它（用户说话时自动打断AI）
        if self.tts.running:
            logger.info("⚠️ 用户开始说话，打断AI语音输出")
            await self._handle_interrupt()

    # =========================================================================
    # 3. 核心数据流 (Data Flow)
    # =========================================================================

    async def _handle_user_input(self, text: str):
        """
        处理用户输入 (来自 ASR 或直接文本输入)。
        如果正在预热新 Session,会将输入记录到增量缓存中。
        
        Args:
            text: 用户输入的文本内容
        """
        if not text or not text.strip(): return

        # 更新状态：思考中
        await self._send_state_update("thinking")

        # 广播用户输入
        await event_bus.publish(EventType.CHAT_RECEIVED, {"content": text})
        self.last_user_input = text

        # 增加对话条数计数
        self.conversation_count += 1

        # [关键] 后台预热新 Session，记录用户对话
        if self.is_preparing_renew:
            self.incremental_cache.append({"role": "user", "content": text})

        # 发送给当前 LLM
        if self.current_llm:
            try:
                # [RAG 集成] 在发送前，先检索长期记忆
                _, rag_context = self.memory_manager.get_context(text)
                if rag_context:
                    # 注入临时上下文到 LLM 的历史中
                    self.current_llm.add_temporary_context(rag_context)

                # 获取 LLM 输出队列
                queue = await self.current_llm.send_user_message(text)

                # 如果之前的消费者任务还在运行，先取消
                if self.consumer_task and not self.consumer_task.done():
                    self.consumer_task.cancel()

                # 启动新的消费者任务
                self.consumer_task = asyncio.create_task(self._consume_llm_queue(queue))

            except Exception as e:
                logger.error(f"Error sending message to LLM: {e}")

    async def _consume_llm_queue(self, queue: asyncio.Queue):
        """
        消费者任务:从 LLM 队列读取 token,处理流式输出。
        
        主要功能:
        - 从队列中读取 LLM 生成的 token
        - 将 token 实时发送到前端 (流式文本)
        - 检测完整句子并发送给 TTS (如果需要音频输出)
        - 更新增量缓存 (如果正在预热新 Session)
        
        Args:
            queue: LLM 输出的异步队列,包含生成的 token
        """
        buffer = ""
        full_response = ""

        # 句子结束符正则 (中英文)
        sentence_endings = re.compile(r'[.!?;。！？；\n]+')

        # 标记是否已开始说话
        has_started_speaking = False

        try:
            while True:
                token = await queue.get()

                # 结束信号
                if token is None:
                    break
                
                # 更新状态：说话中 (仅在收到第一个 token 时发送一次)
                if not has_started_speaking:
                    await self._send_state_update("speaking")
                    has_started_speaking = True

                full_response += token

                # 1. 直接 Websocket 返回给前端 (流式文本)
                await self._send_text_to_frontend(token)

                # 2. 拼接 buffer，检测完整句子 (仅在需要音频输出时)
                if self.output_mode == OutputMode.TEXT_AND_AUDIO:
                    buffer += token

                    # 检查是否有句子结束标记
                    while True:
                        match = sentence_endings.search(buffer)
                        if match:
                            end_pos = match.end()
                            sentence = buffer[:end_pos]
                            remaining = buffer[end_pos:]

                            # 发送完整句子给 TTS
                            if sentence.strip() and not re.fullmatch(r'[^\w\s]+', sentence.strip()):
                                # logger.info(f"Sending sentence to TTS: {sentence[:20]}...")
                                await self.tts.push_text(sentence)
                            else:
                                pass
                                # logger.debug(f"Skipping punctuation-only sentence: {sentence[:20]}")

                            buffer = remaining
                        else:
                            break

                # [关键] 记录增量回复 (兼容热重载逻辑)
                if self.is_preparing_renew:
                    self._update_incremental_cache(token)

            # 循环结束 (None)
            # 处理 buffer 中剩余的内容 (仅在需要音频输出时)
            if self.output_mode == OutputMode.TEXT_AND_AUDIO:
                if buffer.strip() and not re.fullmatch(r'[^\w\s]+', buffer.strip()):
                    # logger.info(f"Sending remaining buffer to TTS: {buffer[:20]}...")
                    await self.tts.push_text(buffer)
                else:
                    pass
                    # logger.debug(f"Skipping punctuation-only buffer: {buffer[:20]}")

            # 触发完成处理
            await self._handle_llm_complete(full_response)

        except asyncio.CancelledError:
            logger.info("LLM consumer task cancelled.")
            # 任务取消时，不需要做特殊处理，TextLLMClient 会处理自己的 task
        except Exception as e:
            logger.error(f"Error in consumer task: {e}")

    def _update_incremental_cache(self, text: str):
        """
        更新增量缓存中的 assistant 消消息。
        如果缓存为空或最后一条不是 assistant 消息,则创建新消息;
        否则追加到现有 assistant 消息中。
        
        Args:
            text: 要添加到缓存的文本内容
        """
        if not self.incremental_cache:
            self.incremental_cache.append({"role": "assistant", "content": text})
            return

        last_msg = self.incremental_cache[-1]
        if last_msg['role'] == 'assistant':
            last_msg['content'] += text
        else:
            self.incremental_cache.append({"role": "assistant", "content": text})

    async def _handle_llm_complete(self, full_text: str):
        """
        LLM 生成结束回调 (Turn End)。
        
        主要功能:
        - 刷新 TTS 队列,确保所有音频播放完成
        - 触发 Agent 分析当前对话历史
        - 检查是否需要执行热切换或启动预热
        
        Args:
            full_text: LLM 生成的完整响应文本
        """
        # 仅在需要音频输出时 flush TTS
        if self.output_mode == OutputMode.TEXT_AND_AUDIO:
            await self.tts.flush()

        # 广播对话完成事件 (用户 + AI)
        if self.last_user_input:
            await event_bus.publish(EventType.CHAT_COMPLETED, {
                "user_content": self.last_user_input,
                "ai_content": full_text
            })
            self.last_user_input = None

        # 更新状态：空闲
        await self._send_state_update("idle")

        # 1. 触发 Agent 分析 (通过队列解耦)
        if self.current_llm:
            current_history = self.current_llm.get_history()

            # 确保 queue 不为空
            if self.queue:
                # 转换 Message 对象为 dict 以便传输
                history_dicts = [{"role": m.role, "content": m.content} for m in current_history]
                await self.queue.put({
                    "type": "analyze_request",
                    "history": history_dicts[-6:]  # 只发最近几轮
                })

        # 2. 检查是否需要热切换
        if self.pending_llm:
            await self._perform_hot_swap()
        else:
            await self._check_renew_condition()

    async def _send_text_to_frontend(self, text: str):
        """
        发送文本到前端 WebSocket。
        
        Args:
            text: 要发送的文本内容
        """
        if self.websocket:
            try:
                # 结构设计：type: "text_stream", content: 文本内容
                await self.websocket.send_text(json.dumps({"type": "text_stream", "content": text}))
            except Exception as e:
                logger.error(f"Failed to send text to frontend: {e}")
    
    async def _send_user_message_to_frontend(self, text: str):
        """
        发送用户消息到前端 WebSocket（用于显示ASR识别结果）。
        
        Args:
            text: 用户消息内容（ASR识别的文字）
        """
        if self.websocket:
            try:
                # 发送用户消息，前端会将其显示为用户气泡
                await self.websocket.send_text(json.dumps({
                    "type": "user_message",
                    "content": text
                }))
            except Exception as e:
                logger.error(f"Failed to send user message to frontend: {e}")

    async def _send_audio_to_frontend(self, audio_data: bytes):
        """
        发送音频数据到前端 WebSocket。
        
        Args:
            audio_data: PCM 格式的音频二进制数据
        """
        if self.websocket:
            try:
                # 结构设计：直接发送二进制 PCM 数据
                # logger.debug(f"Sending audio chunk to frontend: {len(audio_data)} bytes")
                await self.websocket.send_bytes(audio_data)
            except Exception as e:
                logger.error(f"Failed to send audio to frontend: {e}")
                
    async def _send_state_update(self, state: str):
        """
        [发送端] 发送状态变更
        """
        if self.websocket:
            try:
                await self.websocket.send_text(json.dumps({
                    "type": "state_change",
                    "state": state
                }))
            except Exception as e:
                logger.error(f"Send state error: {e}")
    
    async def _send_service_error(self, service: str, error: str):
        """
        发送服务错误到前端
        
        Args:
            service: 服务类型 ("tts" 或 "asr")
            error: 错误信息
        """
        if self.websocket:
            try:
                await self.websocket.send_text(json.dumps({
                    "type": "service_error",
                    "service": service,
                    "error": error
                }))
                logger.warning(f"Service error sent to frontend: {service} - {error}")
            except Exception as e:
                logger.error(f"Failed to send service error: {e}")

    # =========================================================================
    # 4. 真正的无缝热重载
    # =========================================================================

    async def _check_renew_condition(self):
        """
        检查是否需要启动 Session 热重载。
        检测策略根据输入模式而定:
        - 视觉系统输入/实时音频输入: 只检查时间(10分钟)
        - 文本输入/普通音频输入: 只检查对话条数(10条)
        """
        if self.is_preparing_renew: return

        # 判断是否为实时交互模式
        is_realtime_mode = self.input_mode in [InputMode.REALTIME_AUDIO, InputMode.VISION]
        
        should_renew = False
        reason = ""
        
        if is_realtime_mode:
            # 实时音频或视觉输入: 只检查时间
            time_exceeded = time.time() - self.session_start_time > self.renew_threshold
            if time_exceeded:
                reason = f"时间超过 {self.renew_threshold}s"
                should_renew = True
        else:
            # 文本或普通音频输入: 只检查对话条数
            conversation_exceeded = self.conversation_count > self.conversation_threshold
            if conversation_exceeded:
                reason = f"对话条数超过 {self.conversation_threshold} 条"
                should_renew = True
        
        if should_renew:
            print(f"Renew threshold reached ({reason}). Preparing shadow session...")
            asyncio.create_task(self._prepare_shadow_session())

    async def _prepare_shadow_session(self):
        """
        后台预热影子会话 (Shadow Session)。
        
        在不影响当前服务的情况下,创建并预热新的 LLM Session。
        预热完成后,系统会开始记录增量对话到缓存中,
        以便切换时能够同步这段时间内的对话历史。
        """
        self.is_preparing_renew = True
        self.incremental_cache = []  # 清空增量缓存

        try:
            # 1. 如果有旧会话，先进行总结 (Summarize & Extract)
            summary_text = ""
            if self.current_llm:
                old_history = self.current_llm.get_history()
                if old_history:
                    logger.info("Summarizing previous session for context injection...")
                    # 异步生成总结（只存储总结，不存储原始对话）
                    session_id = generate_session_id()
                    summary_text = await self.memory_manager.summarize_session(
                        old_history, 
                        session_id=session_id
                    )

            # 2. 创建新 Session (此时会自动拉取最新的 Memory)
            self.pending_llm = await self._create_llm_session(is_renew=True)

            # 3. 注入上一轮的总结作为 Context
            if summary_text:
                self.pending_llm.set_previous_summary(summary_text)

            # 4. 预热 (Warmup) - 用于预热新的会话，加快第一次响应速度，可选
            # await self.pending_llm.warmup()

            print("Shadow session ready. Caching incremental chats...")
            # 此时，_handle_user_input 开始往 incremental_cache 里写数据

        except Exception as e:
            print(f"Renew failed: {e}")
            logger.error(f"Renew failed details: {e}", exc_info=True)
            self.is_preparing_renew = False
            self.pending_llm = None

    async def _perform_hot_swap(self):
        """
        执行热切换,核心在于"状态注入"。
        
        热切换流程:
        1. 将预热期间产生的增量对话注入到新 Session
        2. 切换指针,使新 Session 成为当前服务的 Session
        3. 重置相关状态标志
        4. 延迟关闭旧 Session,确保尾音播放完成
        """
        if not self.pending_llm: return
        self.is_swapping = True

        print(f"Swapping sessions. Syncing {len(self.incremental_cache)} new messages...")

        # [关键] 1. 将预热期间产生的对话注入到新 Session
        # 这样新 Session 就"知道"刚才那十几秒发生了什么
        if self.incremental_cache:
            await self.pending_llm.inject_history(self.incremental_cache)

        # 2. 指针切换
        old_llm = self.current_llm
        self.current_llm = self.pending_llm

        # 3. 重置状态
        self.pending_llm = None
        self.incremental_cache = []
        self.is_preparing_renew = False
        self.session_start_time = time.time()
        self.conversation_count = 0  # 重置对话条数计数器
        self.is_swapping = False

        # 4. 延迟关闭旧 Session (防止还有尾音没播完)
        asyncio.create_task(self._safe_close(old_llm))
        print("Session swapped successfully.")

    async def _safe_close(self, session: TextLLMClient):
        """
        安全关闭旧 Session。
        延迟 5 秒后关闭,确保所有音频播放完成。
        
        Args:
            session: 要关闭的 TextLLMClient 实例
        """
        await asyncio.sleep(5)
        await session.close()

    # =========================================================================
    # 5. 辅助方法
    # =========================================================================

    async def _create_llm_session(self, is_renew: bool = False) -> TextLLMClient:
        """
        创建并初始化 LLM Session 实例。
        
        Args:
            is_renew: 是否为热重载创建。如果为 True,表示这是后台预热的 Session,
                     不会立即绑定到当前 UI 输出,而是静默运行
        
        Returns:
            TextLLMClient: 已连接的 LLM 客户端实例
        """
        # 构建个性化系统提示词（融合用户信息）
        system_prompt = build_personalized_system_prompt(
            user_name=settings.user_profile.name,
            user_nickname=settings.user_profile.nickname,
            user_age=settings.user_profile.age,
            user_gender=settings.user_profile.gender,
            relationship_with_ai=settings.user_profile.relationship_with_ai,
            long_term_context=""  # 这里为空，在对话时通过 RAG 注入
        )
        
        llm = TextLLMClient(system_prompt=system_prompt)
        await llm.connect()
        return llm

    async def _handle_interrupt(self):
        """
        处理用户打断事件。
        
        当检测到用户打断 (通常来自 VAD) 时:
        - 清空 TTS 队列,停止当前音频播放
        - 取消正在运行的消费者任务
        - 取消 LLM 的生成任务
        """
        print("User Interrupt!")
        
        # 更新状态：被打断
        await self._send_state_update("interrupted")

        # 仅在需要音频输出时清空 TTS 队列
        if self.output_mode == OutputMode.TEXT_AND_AUDIO:
            await self.tts.clear_queue()

        # 取消当前的消费者任务
        if self.consumer_task and not self.consumer_task.done():
            self.consumer_task.cancel()

        # 清空 ASR 缓冲，避免残留音频影响后续识别
        if self.asr:
            await self.asr.clear_buffer()

        # 取消 LLM 生成
        if self.current_llm:
            await self.current_llm.cancel()

        # 恢复空闲状态
        await self._send_state_update("idle")

    async def _handle_hot_reload(self):
        """
        处理主动热更新请求。
        
        与正常的 renew 不同，热更新不会：
        1. 总结之前的对话
        2. 将历史总结注入到新会话的系统提示词中
        
        但会保留：
        - 记忆系统中的所有数据（只是不在当前会话上下文中使用）
        - 任务跟踪和其他系统状态
        """
        logger.info("🔄 [Hot Reload] 收到热更新请求，开始重置会话上下文...")
        
        try:
            # 1. 停止当前正在进行的任何操作
            if self.consumer_task and not self.consumer_task.done():
                self.consumer_task.cancel()
            
            if self.current_llm:
                await self.current_llm.cancel()
            
            # 2. 清理 TTS 队列
            if self.output_mode == OutputMode.TEXT_AND_AUDIO:
                await self.tts.clear_queue()
            
            # 3. 清空 ASR 缓冲
            if self.asr:
                await self.asr.clear_buffer()
            
            # 4. 重置会话计数和状态
            self.conversation_count = 0
            self.is_preparing_renew = False
            self.incremental_cache = []
            
            # 5. 创建新的 LLM 会话（关键：不注入历史总结）
            logger.info("创建新的 LLM 会话（不包含历史总结）...")
            new_llm = await self._create_llm_session(is_renew=False)
            
            # 6. 切换到新会话
            if self.current_llm:
                # 关闭旧会话
                try:
                    await self.current_llm.close()
                except Exception as e:
                    logger.warning(f"关闭旧 LLM 会话失败: {e}")
            
            self.current_llm = new_llm
            self.pending_llm = None
            
            # 7. 更新状态为空闲
            await self._send_state_update("idle")
            
            # 8. 发送确认消息给前端
            await self._send_text_to_frontend("【系统提示】热更新完成，已重置对话上下文。")
            
            logger.info("✅ [Hot Reload] 热更新完成，会话已重置")
            
        except Exception as e:
            logger.error(f"❌ [Hot Reload] 热更新失败: {e}", exc_info=True)
            await self._send_text_to_frontend("【系统错误】热更新失败，请重试。")
            # 恢复空闲状态
            await self._send_state_update("idle")
