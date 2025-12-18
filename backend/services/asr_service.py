import logging
import asyncio

logger = logging.getLogger(__name__)

class ASRService:
    def __init__(self, config):
        self.config = config
        self.running = False
        self.on_transcript = None
        self.on_vad_trigger = None
        
        # 音频缓冲区，用于累积音频数据
        self.audio_buffer = bytearray()
        self.buffer_lock = asyncio.Lock()
        
        # 音频参数（可从 config 读取）
        self.sample_rate = config.get("sample_rate", 16000)  # 采样率 16kHz
        self.channels = config.get("channels", 1)  # 单声道
        self.sample_width = config.get("sample_width", 2)  # 16-bit = 2 bytes

    async def start(self, on_transcript, on_vad_trigger):
        """
        启动 ASR 服务
        
        Args:
            on_transcript: 识别结果回调函数 (text: str) -> None
            on_vad_trigger: VAD 触发回调函数 () -> None
        """
        self.on_transcript = on_transcript
        self.on_vad_trigger = on_vad_trigger
        self.running = True
        logger.info("ASR Service started")
        logger.info(f"Audio config: {self.sample_rate}Hz, {self.channels}ch, {self.sample_width*8}bit")

    async def stop(self):
        """停止 ASR 服务"""
        self.running = False
        async with self.buffer_lock:
            self.audio_buffer.clear()
        logger.info("ASR Service stopped")
    
    async def push_audio_data(self, audio_data: bytes):
        """
        接收音频数据（PCM 格式）
        
        Args:
            audio_data: PCM 音频数据（bytes）
                格式要求：
                - 采样率: 16000 Hz
                - 位深: 16-bit (2 bytes per sample)
                - 声道: 单声道 (Mono)
                - 字节序: Little-endian
        """
        if not self.running:
            logger.warning("ASR service is not running, ignoring audio data")
            return
        
        if not audio_data:
            logger.warning("Received empty audio data")
            return
        
        try:
            async with self.buffer_lock:
                # 将音频数据添加到缓冲区
                self.audio_buffer.extend(audio_data)
                buffer_size = len(self.audio_buffer)
                
                # 计算缓冲区时长（秒）
                bytes_per_second = self.sample_rate * self.channels * self.sample_width
                buffer_duration = buffer_size / bytes_per_second
                
                logger.debug(f"Audio buffer: {buffer_size} bytes ({buffer_duration:.2f}s)")
                
                # TODO: 这里可以集成实际的 ASR 引擎进行语音识别
                # 当前仅做缓冲，实际识别逻辑待实现
                    
        except Exception as e:
            logger.error(f"Error in push_audio_data: {e}", exc_info=True)
    
    async def clear_buffer(self):
        """清空音频缓冲区（用于打断场景）"""
        async with self.buffer_lock:
            self.audio_buffer.clear()
            logger.debug("Audio buffer cleared")
