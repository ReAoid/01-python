import asyncio
import logging
import time
from enum import Enum
from typing import List, Dict, Optional, Callable

# 引入项目现有组件
from backend.utils.config_manager import get_config_manager
from backend.core.message import Message

# 引入服务组件
from backend.services.asr_service import ASRService
from backend.services.tts_service import TTSService
from backend.services.text_llm_client import TextLLMClient

logger = logging.getLogger(__name__)

class InputMode(Enum):
    AUDIO = "audio" # ASR -> LLM -> TTS
    TEXT = "text"   # Text -> LLM -> TTS

# --- 核心 Session Manager ---

class SessionManager:
    def __init__(self, message_queue, config_loader=None):
        # 如果未提供 config_loader，使用默认的 ConfigManager
        self.config_manager = config_loader or get_config_manager()
        # 这里为了兼容 load() 接口，可能需要适配
        # 假设 config_loader 有 load() 方法返回配置对象
        # 或者直接使用 config_manager
        
        # 简单起见，我们直接用 config_manager.get_core_config()
        # 但为了保留 reload 能力，我们需要保留 config_manager 引用
        
        self.queue = message_queue # 用于与 Agent/Monitor 通信
        
        # --- 管道组件 ---
        # 传入配置
        self.asr = ASRService(self.config_manager)
        self.tts = TTSService(self.config_manager)
        
        # --- 双 Session 架构 (实现热切换) ---
        self.current_llm = None     # 当前服务中的 LLM
        self.pending_llm = None     # 后台预热中的 LLM
        
        # --- 热切换关键状态 ---
        self.session_start_time = 0
        self.is_swapping = False
        self.renew_threshold = 600  # 10分钟
        
        # --- [关键] 增量记忆缓存 ---
        # 用于记录在"后台预热期间"产生的新对话，防止切换后失忆
        self.incremental_cache: List[Dict] = [] 
        self.is_preparing_renew = False

        # --- 状态 ---
        self.is_active = False
        self.mode = InputMode.AUDIO
        self.websocket = None

    # =========================================================================
    # 1. 生命周期与管道启动
    # =========================================================================

    async def start(self, websocket, mode=InputMode.AUDIO):
        """系统启动入口"""
        self.websocket = websocket
        self.mode = mode
        self.session_start_time = time.time()
        
        # 1. 启动外围设备 (ASR/TTS)
        if mode == InputMode.AUDIO:
            await self.asr.start(
                on_transcript=self._handle_user_input, # ASR 转录结果 -> LLM
                on_vad_trigger=self._handle_interrupt    # 用户打断 -> 停止生成
            )
        await self.tts.start(on_audio=self._send_audio_to_frontend)
        
        # 2. 启动核心 LLM (冷启动)
        self.current_llm = await self._create_llm_session(is_renew=False)
        
        self.is_active = True
        print(f"System started in {mode} mode.")

    async def stop(self):
        """系统停止"""
        self.is_active = False
        if self.current_llm: await self.current_llm.close()
        if self.pending_llm: await self.pending_llm.close()
        await self.asr.stop()
        await self.tts.stop()

    # =========================================================================
    # 2. 核心数据流 (Data Flow)
    # =========================================================================

    async def _handle_user_input(self, text: str):
        """
        处理用户输入 (来自 ASR 或 直接文本)
        """
        if not text or not text.strip(): return
        
        # [关键] 如果正在后台预热新 Session，需要把这句话记下来！
        if self.is_preparing_renew:
            self.incremental_cache.append({"role": "user", "content": text})
            
        # 发送给当前 LLM
        if self.current_llm:
            await self.current_llm.send_user_message(text)

    async def _handle_llm_token(self, text: str):
        """LLM 生成回调"""
        # 1. 发给 TTS 流式合成
        await self.tts.push_text(text)
        # 2. 发给前端显示
        await self._send_text_to_frontend(text)
        
        # [关键] 记录增量回复
        if self.is_preparing_renew and self.incremental_cache:
            # 简单追加到最后一条 assistant 消息中
            last_msg = self.incremental_cache[-1]
            if last_msg['role'] == 'assistant':
                last_msg['content'] += text
            else:
                self.incremental_cache.append({"role": "assistant", "content": text})
        elif self.is_preparing_renew:
             # 如果缓存为空但收到 token (比如刚刚开始生成)，添加一条 assistant 消息
             self.incremental_cache.append({"role": "assistant", "content": text})

    async def _handle_llm_complete(self):
        """LLM 生成结束回调 (Turn End)"""
        await self.tts.flush()
        
        # 1. 触发 Agent 分析 (通过队列解耦)
        #    模仿 core.py 通知 agent_server
        current_history = self.current_llm.get_history()
        
        # 确保 queue 不为空
        if self.queue:
            # 转换 Message 对象为 dict 以便传输
            history_dicts = [{"role": m.role, "content": m.content} for m in current_history]
            await self.queue.put({
                "type": "analyze_request", 
                "history": history_dicts[-6:] # 只发最近几轮
            })
        
        # 2. 检查是否需要热切换
        if self.pending_llm:
            await self._perform_hot_swap()
        else:
            await self._check_renew_condition()

    async def _send_text_to_frontend(self, text: str):
        if self.websocket:
            try:
                # 假设 websocket 发送 JSON
                import json
                await self.websocket.send_text(json.dumps({"type": "text_stream", "content": text}))
            except Exception as e:
                logger.error(f"Failed to send text to frontend: {e}")

    async def _send_audio_to_frontend(self, audio_data: bytes):
        if self.websocket:
            try:
                # 假设 websocket 支持发送 bytes
                await self.websocket.send_bytes(audio_data)
            except Exception as e:
                logger.error(f"Failed to send audio to frontend: {e}")

    # =========================================================================
    # 3. 真正的无缝热重载 (The "Soul" of Core.py)
    # =========================================================================

    async def _check_renew_condition(self):
        """检查时间或 Token 是否超标"""
        if self.is_preparing_renew: return
        
        if time.time() - self.session_start_time > self.renew_threshold:
            print("Renew threshold reached. Preparing shadow session...")
            asyncio.create_task(self._prepare_shadow_session())

    async def _prepare_shadow_session(self):
        """后台预热影子会话"""
        self.is_preparing_renew = True
        self.incremental_cache = [] # 清空增量缓存
        
        try:
            # 1. 创建新 Session (此时会自动拉取最新的 Memory)
            self.pending_llm = await self._create_llm_session(is_renew=True)
            
            # 2. 预热 (Warmup) - 可选
            # await self.pending_llm.warmup()
            
            print("Shadow session ready. Caching incremental chats...")
            # 此时，_handle_user_input 开始往 incremental_cache 里写数据
            
        except Exception as e:
            print(f"Renew failed: {e}")
            self.is_preparing_renew = False
            self.pending_llm = None

    async def _perform_hot_swap(self):
        """
        执行热切换：核心在于"状态注入"
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
        self.is_swapping = False
        
        # 4. 延迟关闭旧 Session (防止还有尾音没播完)
        asyncio.create_task(self._safe_close(old_llm))
        print("Session swapped successfully.")

    async def _safe_close(self, session):
        await asyncio.sleep(5)
        await session.close()

    # =========================================================================
    # 4. 辅助方法
    # =========================================================================

    async def _create_llm_session(self, is_renew=False):
        """
        创建 LLM 实例
        :param is_renew: 如果是 True，不会绑定到当前 UI 输出，而是静默运行
        """
        # 重新加载配置
        cfg = self.config_manager.get_core_config()
        api_key = cfg.get("LLM_API_KEY")
        
        if not api_key:
            raise ValueError("LLM_API_KEY 未在配置中找到，请检查配置文件或环境变量")

        llm = TextLLMClient(
            api_key=api_key,
            on_token=self._handle_llm_token if not is_renew else None, # 预热时不输出
            on_complete=self._handle_llm_complete if not is_renew else None
        )
        await llm.connect()
        return llm

    async def _handle_interrupt(self):
        """用户打断"""
        print("User Interrupt!")
        await self.tts.clear_queue()
        await self.current_llm.cancel()
