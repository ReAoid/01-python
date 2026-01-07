"""DummyASREngine - ASR 占位实现

提供简单的缓冲和能量阈值 VAD 功能，用于测试和占位
"""

import logging
import struct
from typing import Optional, Dict, Any
from backend.utils.asr.base_engine import BaseASREngine

logger = logging.getLogger(__name__)


class DummyASREngine(BaseASREngine):
    """占位 ASR 引擎，不进行实际语音识别"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # 音频参数
        self.sample_rate: int = config.get("sample_rate", 16000)
        self.channels: int = config.get("channels", 1)
        self.sample_width: int = config.get("sample_width", 2)
        self.min_audio_length: float = config.get("min_audio_length", 0.5)
        
        # VAD 参数
        self.vad_enabled: bool = config.get("vad_enabled", True)
        self.energy_threshold: float = config.get("energy_threshold", 0.01)
        
        # 状态
        self.audio_buffer = bytearray()
        self.last_energy = 0.0
        
    async def initialize(self) -> bool:
        """初始化占位引擎"""
        logger.info("DummyASREngine initialized")
        logger.info(f"Audio config: {self.sample_rate}Hz, "
                   f"{self.channels}ch, "
                   f"{self.sample_width * 8}bit")
        return True
    
    async def process_audio(self, audio_data: bytes) -> Optional[str]:
        """
        缓冲音频，达到阈值后返回占位文本
        
        Args:
            audio_data: PCM 音频数据
            
        Returns:
            当缓冲区积累足够长度时返回占位文本，否则返回 None
        """
        self.audio_buffer.extend(audio_data)
        
        # 计算缓冲区时长
        bytes_per_second = self.sample_rate * self.channels * self.sample_width
        buffer_duration = len(self.audio_buffer) / bytes_per_second
        
        # 如果达到最小长度阈值，返回占位文本并清空缓冲
        if buffer_duration >= self.min_audio_length:
            text = f"[DummyASR] 收到 {buffer_duration:.2f}秒 音频"
            logger.info(f"DummyASR recognized: {text}")
            self.audio_buffer.clear()
            return text
        
        return None
    
    async def detect_vad(self, audio_data: bytes) -> bool:
        """
        简单的能量阈值 VAD 检测
        
        Args:
            audio_data: PCM 音频数据
            
        Returns:
            检测到语音活动返回 True
        """
        if not self.vad_enabled:
            return False
        
        # 计算音频能量
        energy = self._calculate_energy(audio_data)
        self.last_energy = energy
        
        # 能量超过阈值视为语音活动
        is_speech = energy > self.energy_threshold
        
        if is_speech:
            logger.debug(f"VAD triggered: energy={energy:.4f}")
        
        return is_speech
    
    def _calculate_energy(self, audio_data: bytes) -> float:
        """
        计算音频能量（RMS）
        
        Args:
            audio_data: PCM 音频数据
            
        Returns:
            归一化能量值 [0, 1]
        """
        if len(audio_data) < self.sample_width:
            return 0.0
        
        # 解析 PCM 样本
        sample_count = len(audio_data) // self.sample_width
        samples = struct.unpack(f"<{sample_count}h", audio_data[:sample_count * 2])
        
        # 计算 RMS
        sum_squares = sum(s * s for s in samples)
        rms = (sum_squares / sample_count) ** 0.5
        
        # 归一化到 [0, 1]
        max_amplitude = 32768.0  # 16-bit PCM
        return rms / max_amplitude
    
    async def clear_buffer(self):
        """清空音频缓冲区"""
        self.audio_buffer.clear()
        logger.debug("DummyASR buffer cleared")
    
    async def shutdown(self):
        """关闭占位引擎"""
        self.audio_buffer.clear()
        logger.info("DummyASREngine shutdown")
