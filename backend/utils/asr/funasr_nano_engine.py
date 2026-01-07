"""
基于 Fun-ASR-Nano 的 ASR 引擎实现。

在子进程中使用，通过 ONNX Runtime 进行本地语音识别，提供流式 ASR 功能。
"""

import logging
import numpy as np
import struct
from typing import Optional, List, Dict, Any
from pathlib import Path

from .base_engine import BaseASREngine

logger = logging.getLogger(__name__)

# 延迟导入，避免没有安装 onnxruntime 时启动失败
try:
    import onnxruntime as ort
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False
    logger.warning("onnxruntime not installed, FunASRNanoEngine will not work")


class FunASRNanoEngine(BaseASREngine):
    """Fun-ASR-Nano 引擎实现。"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化引擎
        
        Args:
            config: ASR 引擎配置字典
        """
        self.config = config
        
        # ONNX 模型相关
        self.model_path: Optional[Path] = None
        self.device: str = config.get("device", "cpu")
        self.session: Optional[ort.InferenceSession] = None
        
        # 音频参数
        self.sample_rate: int = config.get("sample_rate", 16000)
        self.channels: int = config.get("channels", 1)
        self.sample_width: int = config.get("sample_width", 2)
        self.min_audio_length: float = config.get("min_audio_length", 1.0)
        
        # VAD 参数
        self.vad_enabled: bool = config.get("vad_enabled", True)
        self.energy_threshold: float = config.get("energy_threshold", 0.01)
        self.aggressiveness: int = config.get("aggressiveness", 3)
        
        # 状态
        self.audio_buffer = bytearray()
        self.speech_frames = 0
        self.silence_frames = 0
        
        # 词汇表（简化版，实际需要从模型配置加载）
        self.vocab = self._build_dummy_vocab()

    def _build_dummy_vocab(self) -> dict:
        """构建简化的词汇表（占位）"""
        # 实际应从模型配置加载完整词表
        return {i: chr(i + 65) for i in range(26)}  # A-Z

    async def initialize(self) -> bool:
        """初始化 ASR 引擎并加载 ONNX 模型。"""
        if not ONNX_AVAILABLE:
            logger.error("onnxruntime 未安装，无法使用 FunASRNanoEngine")
            return False
        
        try:
            # 获取模型路径
            model_path_str = self.config.get("model_path")
            if not model_path_str:
                logger.error("Model path not configured")
                return False
            
            self.model_path = Path(model_path_str)
            
            # 检查模型文件是否存在
            if not self.model_path.exists():
                logger.error(f"模型文件不存在: {self.model_path}")
                return False
            
            # 配置 ONNX Runtime
            logger.info(f"正在加载 Fun-ASR-Nano 模型: {self.model_path}")
            providers = ['CPUExecutionProvider']
            if self.device == 'cuda':
                providers.insert(0, 'CUDAExecutionProvider')
            
            self.session = ort.InferenceSession(
                str(self.model_path),
                providers=providers
            )
            
            logger.info(f"✅ Fun-ASR-Nano 模型加载成功")
            logger.info(f"设备: {self.device}, Providers: {self.session.get_providers()}")
            logger.info(f"VAD: {'启用' if self.vad_enabled else '禁用'}, 阈值: {self.energy_threshold}")
            
            return True
            
        except Exception as e:
            logger.error(f"初始化 FunASRNanoEngine 失败: {e}", exc_info=True)
            return False

    async def process_audio(self, audio_data: bytes) -> Optional[str]:
        """
        处理音频数据，进行语音识别
        
        Args:
            audio_data: PCM 音频数据
            
        Returns:
            识别出的文本，如果没有识别结果返回 None
        """
        if self.session is None:
            logger.error("引擎未初始化")
            return None
        
        try:
            # 添加到缓冲区
            self.audio_buffer.extend(audio_data)
            
            # 检查缓冲区长度
            bytes_per_second = self.sample_rate * self.channels * self.sample_width
            buffer_duration = len(self.audio_buffer) / bytes_per_second
            
            # 达到最小长度才进行识别
            if buffer_duration < self.min_audio_length:
                return None
            
            # 预处理音频
            features = self._extract_features(bytes(self.audio_buffer))
            if features is None:
                logger.warning("特征提取失败")
                return None
            
            # 模型推理
            token_ids = self._infer(features)
            if token_ids is None:
                logger.warning("模型推理失败")
                return None
            
            # Token IDs -> Text (简化版解码)
            text = self._decode_tokens(token_ids)
            
            if text:
                logger.info(f"ASR 识别: {text} ({buffer_duration:.2f}s)")
                self.audio_buffer.clear()
                self._reset_vad()
                return text
            
            return None
            
        except Exception as e:
            logger.error(f"处理音频时出错: {e}", exc_info=True)
            return None

    def _pcm_to_float(self, pcm_data: bytes) -> Optional[np.ndarray]:
        """
        将 PCM 数据转换为归一化的 float32 数组
        
        Args:
            pcm_data: PCM 音频数据 (16-bit little-endian)
            
        Returns:
            归一化后的音频数组 [-1, 1]，失败返回 None
        """
        try:
            if len(pcm_data) < self.sample_width:
                return None
            
            # 解析 PCM 样本
            sample_count = len(pcm_data) // self.sample_width
            samples = struct.unpack(f"<{sample_count}h", pcm_data[:sample_count * 2])
            
            # 转换为 numpy 数组并归一化
            audio_array = np.array(samples, dtype=np.float32)
            audio_array = audio_array / 32768.0  # 16-bit PCM 归一化
            
            return audio_array
            
        except Exception as e:
            logger.error(f"PCM 转换失败: {e}")
            return None

    def _extract_features(self, pcm_data: bytes) -> Optional[np.ndarray]:
        """
        提取音频特征（简化版，实际可能需要 MFCC/Fbank）
        
        Args:
            pcm_data: PCM 音频数据
            
        Returns:
            模型输入特征，失败返回 None
        """
        try:
            # Step 1: PCM -> float array
            audio_array = self._pcm_to_float(pcm_data)
            if audio_array is None:
                return None
            
            # Step 2: 简单的分帧处理
            frame_length = int(0.025 * self.sample_rate)  # 25ms
            frame_shift = int(0.010 * self.sample_rate)   # 10ms
            
            num_frames = (len(audio_array) - frame_length) // frame_shift + 1
            if num_frames <= 0:
                return None
            
            # 构造特征矩阵
            features = np.zeros((num_frames, frame_length), dtype=np.float32)
            for i in range(num_frames):
                start = i * frame_shift
                end = start + frame_length
                features[i] = audio_array[start:end]
            
            # 添加 batch 维度
            features = np.expand_dims(features, axis=0)
            
            return features
            
        except Exception as e:
            logger.error(f"特征提取失败: {e}")
            return None

    def _infer(self, audio_features: np.ndarray) -> Optional[List[int]]:
        """
        模型推理
        
        Args:
            audio_features: 音频特征 (numpy array)
            
        Returns:
            识别出的 token IDs，失败返回 None
        """
        if self.session is None:
            logger.error("模型未加载")
            return None
        
        try:
            # 执行推理
            input_name = self.session.get_inputs()[0].name
            output_name = self.session.get_outputs()[0].name
            
            outputs = self.session.run(
                [output_name],
                {input_name: audio_features}
            )
            
            # 返回 token IDs
            return outputs[0].tolist()
            
        except Exception as e:
            logger.error(f"推理失败: {e}", exc_info=True)
            return None

    def _decode_tokens(self, token_ids: list) -> str:
        """
        将 token IDs 解码为文本
        
        Args:
            token_ids: Token ID 列表
            
        Returns:
            解码后的文本
        """
        try:
            # 过滤特殊 token (如 <sos>, <eos>, <pad>)
            filtered_tokens = [tid for tid in token_ids if tid < len(self.vocab)]
            
            if not filtered_tokens:
                return ""
            
            # 映射到字符
            chars = [self.vocab.get(tid, '?') for tid in filtered_tokens]
            return ''.join(chars)
            
        except Exception as e:
            logger.error(f"Token 解码失败: {e}")
            return ""

    async def detect_vad(self, audio_data: bytes) -> bool:
        """
        检测语音活动
        
        Args:
            audio_data: PCM 音频数据
            
        Returns:
            检测到语音活动返回 True
        """
        if not self.vad_enabled:
            return False
        
        energy = self._calculate_energy(audio_data)
        
        # 基于能量阈值的简单 VAD
        is_speech = energy > self.energy_threshold
        
        # 状态平滑
        if is_speech:
            self.speech_frames += 1
            self.silence_frames = 0
        else:
            self.silence_frames += 1
            if self.silence_frames > 10:  # 连续 10 帧静音
                self.speech_frames = 0
        
        # 需要连续若干帧语音才触发
        min_speech_frames = 3  # 根据 aggressiveness 调整
        if self.aggressiveness == 0:
            min_speech_frames = 1
        elif self.aggressiveness == 1:
            min_speech_frames = 2
        elif self.aggressiveness == 2:
            min_speech_frames = 3
        else:  # aggressiveness == 3
            min_speech_frames = 5
        
        return self.speech_frames >= min_speech_frames

    def _calculate_energy(self, pcm_data: bytes) -> float:
        """
        计算音频能量 (RMS)
        
        Args:
            pcm_data: PCM 音频数据
            
        Returns:
            归一化能量值 [0, 1]
        """
        try:
            if len(pcm_data) < self.sample_width:
                return 0.0
            
            # 解析 PCM 样本
            sample_count = len(pcm_data) // self.sample_width
            samples = struct.unpack(f"<{sample_count}h", pcm_data[:sample_count * 2])
            
            # 计算 RMS
            sum_squares = sum(s * s for s in samples)
            rms = (sum_squares / sample_count) ** 0.5
            
            # 归一化到 [0, 1]
            max_amplitude = 32768.0  # 16-bit PCM
            return rms / max_amplitude
            
        except Exception as e:
            logger.error(f"能量计算失败: {e}")
            return 0.0

    def _reset_vad(self):
        """重置 VAD 状态"""
        self.speech_frames = 0
        self.silence_frames = 0

    async def clear_buffer(self):
        """清空音频缓冲区"""
        self.audio_buffer.clear()
        self._reset_vad()
        logger.debug("FunASRNano buffer cleared")

    async def shutdown(self):
        """关闭 ASR 引擎"""
        self.session = None
        self.audio_buffer.clear()
        logger.info("FunASRNanoEngine shutdown")
