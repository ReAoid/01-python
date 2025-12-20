import asyncio
import logging
import time
import json
from enum import Enum
from typing import List, Dict, Optional, Callable
import re

from fastapi import WebSocket, WebSocketDisconnect

# 引入项目现有组件
from backend.config import settings

# 引入服务组件
from backend.services.asr_service import ASRService
from backend.services.tts_service import TTSService
from backend.services.text_llm_client import TextLLMClient

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
    
    def __init__(self, message_queue: asyncio.Queue, config_loader=None):
        """
        初始化会话管理器。
        
        Args:
            message_queue: 用于与 Agent/Monitor 通信的异步队列
            config_loader: 配置加载器 (已废弃，保留兼容性)
        """
        # 加载配置
        self.config = settings
        # 用于与 Agent/Monitor 通信
        self.queue = message_queue

        # --- 管道组件 ---
        # ASRService 需要字典配置
        asr_config = {
            "sample_rate": 16000,
            "channels": 1,
            "sample_width": 2
        }
        self.asr = ASRService(asr_config)
        # TTSService 使用 settings 对象
        self.tts = TTSService(self.config)

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
        if input_mode == InputMode.AUDIO:
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
        
        logger.info(
            f"System components initialized in {time.time() - start_time:.2f}s (input: {input_mode.value}, output: {output_mode.value}).")

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
                    self.input_mode = InputMode(data["input_mode"])
                except ValueError:
                    pass
            if "output_mode" in data:
                try:
                    new_mode = OutputMode(data["output_mode"])
                    
                    # 关键修复：如果切换到含音频模式且 TTS 未运行，则立即启动
                    if new_mode == OutputMode.TEXT_AND_AUDIO and not self.tts.running:
                        logger.info("Switching to Audio mode: Lazy starting TTS service...")
                        # 启动 TTS，传入音频回调
                        await self.tts.start(on_audio=self._send_audio_to_frontend)
                        
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

        # 增加对话条数计数
        self.conversation_count += 1

        # [关键] 后台预热新 Session，记录用户对话
        if self.is_preparing_renew:
            self.incremental_cache.append({"role": "user", "content": text})

        # 发送给当前 LLM
        if self.current_llm:
            try:
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

        try:
            while True:
                token = await queue.get()

                # 结束信号
                if token is None:
                    break

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
                            if sentence.strip():
                                await self.tts.push_text(sentence)

                            buffer = remaining
                        else:
                            break

                # [关键] 记录增量回复 (兼容热重载逻辑)
                if self.is_preparing_renew:
                    self._update_incremental_cache(token)

            # 循环结束 (None)
            # 处理 buffer 中剩余的内容 (仅在需要音频输出时)
            if self.output_mode == OutputMode.TEXT_AND_AUDIO and buffer.strip():
                await self.tts.push_text(buffer)

            # 触发完成处理
            await self._handle_llm_complete(full_response)

        except asyncio.CancelledError:
            logger.info("LLM consumer task cancelled.")
            # 任务取消时，不需要做特殊处理，TextLLMClient 会处理自己的 task
        except Exception as e:
            logger.error(f"Error in consumer task: {e}")

    def _update_incremental_cache(self, text: str):
        """
        更新增量缓存中的 assistant 消息。
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

    async def _send_audio_to_frontend(self, audio_data: bytes):
        """
        发送音频数据到前端 WebSocket。
        
        Args:
            audio_data: PCM 格式的音频二进制数据
        """
        if self.websocket:
            try:
                # 结构设计：直接发送二进制 PCM 数据
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
            # 1. 创建新 Session (此时会自动拉取最新的 Memory)
            self.pending_llm = await self._create_llm_session(is_renew=True)

            # 2. 预热 (Warmup) - 用于预热新的会话，加快第一次响应速度，可选
            # await self.pending_llm.warmup()

            print("Shadow session ready. Caching incremental chats...")
            # 此时，_handle_user_input 开始往 incremental_cache 里写数据

        except Exception as e:
            print(f"Renew failed: {e}")
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
        # todo 补充人设输入
        llm = TextLLMClient()

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

        # 仅在需要音频输出时清空 TTS 队列
        if self.output_mode == OutputMode.TEXT_AND_AUDIO:
            await self.tts.clear_queue()

        # 取消当前的消费者任务
        if self.consumer_task and not self.consumer_task.done():
            self.consumer_task.cancel()

        # 取消 LLM 生成
        if self.current_llm:
            await self.current_llm.cancel()
