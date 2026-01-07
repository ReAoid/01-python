"""
ASR 引擎抽象基类

定义所有 ASR 引擎必须实现的接口
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class BaseASREngine(ABC):
    """ASR 引擎抽象基类"""
    
    @abstractmethod
    async def initialize(self) -> bool:
        """
        初始化 ASR 引擎（加载模型、建立连接等）
        
        Returns:
            bool: 初始化成功返回 True，失败返回 False
        """
        pass
    
    @abstractmethod
    async def process_audio(self, audio_data: bytes) -> Optional[str]:
        """
        处理音频数据，进行语音识别
        
        Args:
            audio_data: PCM 音频数据
            
        Returns:
            Optional[str]: 识别出的文本，如果没有识别结果返回 None
        """
        pass
    
    @abstractmethod
    async def detect_vad(self, audio_data: bytes) -> bool:
        """
        检测语音活动（Voice Activity Detection）
        
        Args:
            audio_data: PCM 音频数据
            
        Returns:
            bool: 检测到语音活动返回 True
        """
        pass
    
    @abstractmethod
    async def clear_buffer(self):
        """清空内部音频缓冲区（用于打断场景）"""
        pass
    
    @abstractmethod
    async def shutdown(self):
        """关闭 ASR 引擎，释放资源"""
        pass
