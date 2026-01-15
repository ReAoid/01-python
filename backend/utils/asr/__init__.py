"""ASR (Automatic Speech Recognition) 引擎抽象层

提供统一的 ASR 接口，支持多种 ASR 引擎实现
"""

from backend.utils.asr.base_engine import BaseASREngine
from backend.utils.asr.dummy_engine import DummyASREngine
from backend.utils.asr.funasr_engine import FunASREngine

__all__ = ["BaseASREngine", "DummyASREngine", "FunASREngine"]
