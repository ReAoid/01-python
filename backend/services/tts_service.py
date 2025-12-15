"""
TTS 服务
集成 Genie TTS 实现流式语音合成
"""
import asyncio
import logging
import os
import json
from pathlib import Path
from typing import Optional, Callable

from backend.utils.genie_tts import GenieTTS

logger = logging.getLogger(__name__)


class TTSService:
    """
    TTS 服务封装
    使用 Genie TTS 实现流式语音合成
    """
    
    def __init__(self, config):
        """
        初始化 TTS 服务
        
        Args:
            config: ConfigManager 实例或配置字典
        """
        self.config = config
        self.queue = asyncio.Queue()
        self.running = False
        self.on_audio: Optional[Callable] = None
        
        # Genie TTS 客户端
        self.genie_client: Optional[GenieTTS] = None
        
        # TTS 配置（从 config 中读取）
        self.tts_config = self._load_tts_config()

    def _load_tts_config(self) -> dict:
        """从配置管理器加载 TTS 配置（仅支持新格式）"""
        # 如果 config 是 ConfigManager 对象
        if hasattr(self.config, 'get_core_config'):
            core_config = self.config.get_core_config()
            
            # 获取 TTS 服务配置
            tts_config = core_config.get('tts', {})
            
            # 获取角色库配置
            characters = core_config.get('tts_characters', {})
            
            # 获取当前激活的角色
            active_character = tts_config.get('active_character', 'feibi')
            character_config = characters.get(active_character, {})
            
            # 合并配置：角色配置优先
            merged_config = {
                'enabled': tts_config.get('enabled', True),
                'host': tts_config.get('server', {}).get('host', '127.0.0.1'),
                'port': tts_config.get('server', {}).get('port', 8000),
                'character': active_character,
                'language': character_config.get('language', tts_config.get('language', 'zh')),
                'model_dir': character_config.get('model_dir'),
                'reference_audio_path': character_config.get('reference_audio', {}).get('path'),
                'reference_audio_text': character_config.get('reference_audio', {}).get('text'),
                'reference_audio_mode': character_config.get('reference_audio', {}).get('mode', 'Normal'),
            }
            
            return merged_config
            
        elif isinstance(self.config, dict):
            tts_config = self.config.get('tts', {})
            characters = self.config.get('tts_characters', {})
            active_character = tts_config.get('active_character', 'feibi')
            character_config = characters.get(active_character, {})
            
            return {
                'enabled': tts_config.get('enabled', True),
                'host': tts_config.get('server', {}).get('host', '127.0.0.1'),
                'port': tts_config.get('server', {}).get('port', 8000),
                'character': active_character,
                'language': character_config.get('language', 'zh'),
                'model_dir': character_config.get('model_dir'),
                'reference_audio_path': character_config.get('reference_audio', {}).get('path'),
                'reference_audio_text': character_config.get('reference_audio', {}).get('text'),
                'reference_audio_mode': character_config.get('reference_audio', {}).get('mode', 'Normal'),
            }
        else:
            logger.warning("无法从配置中读取 TTS 配置，使用默认值")
            return {}

    async def start(self, on_audio: Callable):
        """
        启动 TTS 服务
        
        Args:
            on_audio: 音频数据回调函数 async def on_audio(audio_bytes: bytes)
        """
        self.on_audio = on_audio
        self.running = True
        
        # 1. 初始化 Genie 客户端
        host = self.tts_config.get('host', '127.0.0.1')
        port = self.tts_config.get('port', 8000)
        
        self.genie_client = GenieTTS(host=host, port=port)
        
        # 2. 连接到 Genie TTS 服务器（带重试）
        max_retries = 5
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                logger.info(f"尝试连接到 Genie TTS 服务器 ({attempt + 1}/{max_retries})...")
                if await self.genie_client.connect(timeout=5):
                    break
            except Exception as e:
                logger.warning(f"连接失败: {e}")
            
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
        else:
            logger.error("无法连接到 Genie TTS 服务器，TTS 功能将不可用")
            self.genie_client = None
            asyncio.create_task(self._process_queue())  # 启动队列处理（但不会有音频输出）
            return
        
        # 3. 加载角色模型
        character_name = self.tts_config.get('character', 'feibi')
        model_dir = self.tts_config.get('model_dir')
        language = self.tts_config.get('language', 'zh')
        
        if not model_dir:
            # 尝试自动查找模型目录
            model_dir = self._find_character_model(character_name)
        
        if model_dir and os.path.exists(model_dir):
            logger.info(f"加载角色模型: {character_name} 从 {model_dir}")
            if not await self.genie_client.load_character(character_name, model_dir, language):
                logger.error("加载角色模型失败")
                self.genie_client = None
                asyncio.create_task(self._process_queue())
                return
        else:
            logger.error(f"未找到角色模型目录: {model_dir}")
            self.genie_client = None
            asyncio.create_task(self._process_queue())
            return
        
        # 4. 设置参考音频
        ref_audio_path = self.tts_config.get('reference_audio_path')
        ref_audio_text = self.tts_config.get('reference_audio_text')
        
        if not ref_audio_path or not ref_audio_text:
            # 尝试从 prompt_wav.json 自动加载
            ref_audio_path, ref_audio_text = self._load_reference_audio(model_dir)
        
        if ref_audio_path and ref_audio_text and os.path.exists(ref_audio_path):
            logger.info(f"设置参考音频: {ref_audio_path}")
            if not await self.genie_client.set_reference_audio(ref_audio_path, ref_audio_text, language):
                logger.error("设置参考音频失败")
                self.genie_client = None
                asyncio.create_task(self._process_queue())
                return
        else:
            logger.error(f"未找到参考音频: {ref_audio_path}")
            self.genie_client = None
            asyncio.create_task(self._process_queue())
            return
        
        # 5. 启动队列处理任务
        asyncio.create_task(self._process_queue())
        logger.info("✓ TTS Service 启动成功")

    async def stop(self):
        """停止 TTS 服务"""
        self.running = False
        
        if self.genie_client:
            await self.genie_client.close()
        
        logger.info("TTS Service stopped")

    async def push_text(self, text: str):
        """
        推送文本到合成队列
        
        Args:
            text: 要合成的文本
        """
        if text and text.strip():
            await self.queue.put(text)

    async def flush(self):
        """等待队列处理完毕"""
        await self.queue.join()

    async def clear_queue(self):
        """清空待播放队列"""
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
                self.queue.task_done()
            except asyncio.QueueEmpty:
                break
        logger.info("TTS 队列已清空")

    async def _process_queue(self):
        """处理合成队列（后台任务）"""
        logger.info("TTS 队列处理任务已启动")
        
        while self.running:
            try:
                # 从队列获取文本
                text = await self.queue.get()
                
                if not text or not text.strip():
                    self.queue.task_done()
                    continue
                
                # 如果 Genie 客户端可用，进行合成
                if self.genie_client and self.genie_client.is_ready:
                    try:
                        logger.debug(f"合成文本: {text[:50]}...")
                        
                        # 流式合成并发送音频
                        async for audio_chunk in self.genie_client.synthesize_stream(text):
                            if self.on_audio:
                                await self.on_audio(audio_chunk)
                        
                        logger.debug("✓ 音频合成完成")
                        
                    except Exception as e:
                        logger.error(f"TTS 合成失败: {e}")
                else:
                    # 如果 Genie 不可用，记录警告（Mock 模式）
                    logger.warning(f"TTS 不可用，跳过合成: {text[:50]}...")
                    if self.on_audio:
                        # 发送模拟数据
                        await self.on_audio(f"[Mock Audio] {text}".encode('utf-8'))
                
                self.queue.task_done()
                
            except asyncio.CancelledError:
                logger.info("TTS 队列处理任务被取消")
                break
            except Exception as e:
                logger.error(f"TTS 队列处理异常: {e}")
                self.queue.task_done()
        
        logger.info("TTS 队列处理任务已停止")

    def _find_character_model(self, character_name: str) -> Optional[str]:
        """
        自动查找角色模型目录
        
        Args:
            character_name: 角色名称
            
        Returns:
            模型目录路径，如果未找到则返回 None
        """
        # 搜索路径（按优先级排序）
        search_paths = []
        
        # 优先级 1: 环境变量指定的路径
        genie_data_dir = os.environ.get('GENIE_DATA_DIR')
        if genie_data_dir:
            search_paths.append(Path(genie_data_dir) / 'CharacterModels')
        
        # 优先级 2: backend/config/tts/CharacterModels（默认位置）
        search_paths.append(Path(__file__).parent.parent / 'config' / 'tts' / 'CharacterModels')
        
        # 搜索模型目录
        for base_path in search_paths:
            # 尝试 v2ProPlus 版本
            model_path = base_path / 'v2ProPlus' / character_name / 'tts_models'
            if model_path.exists() and (model_path / 't2s_encoder_fp32.onnx').exists():
                logger.info(f"找到角色模型: {model_path}")
                return str(model_path.absolute())
        
        logger.warning(f"未找到角色 '{character_name}' 的模型目录")
        return None

    def _load_reference_audio(self, model_dir: str) -> tuple[Optional[str], Optional[str]]:
        """
        从 prompt_wav.json 加载参考音频配置
        
        Args:
            model_dir: 模型目录路径
            
        Returns:
            (audio_path, audio_text) 元组
        """
        try:
            character_dir = Path(model_dir).parent
            prompt_wav_json = character_dir / 'prompt_wav.json'
            
            if not prompt_wav_json.exists():
                logger.warning(f"未找到 prompt_wav.json: {prompt_wav_json}")
                return None, None
            
            with open(prompt_wav_json, 'r', encoding='utf-8') as f:
                prompt_config = json.load(f)
            
            # 获取第一个可用的参考音频配置
            audio_config = None
            if 'Normal' in prompt_config:
                audio_config = prompt_config['Normal']
            elif prompt_config:
                audio_config = list(prompt_config.values())[0]
            
            if audio_config:
                audio_filename = audio_config.get('wav')
                audio_text = audio_config.get('text')
                audio_path = character_dir / 'prompt_wav' / audio_filename
                
                if audio_path.exists():
                    logger.info(f"找到参考音频: {audio_filename}")
                    return str(audio_path.absolute()), audio_text
            
        except Exception as e:
            logger.error(f"加载参考音频配置失败: {e}")
        
        return None, None
