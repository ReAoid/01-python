"""FunASR 引擎实现

基于 FunASR 实现完整的语音识别功能，包括：
- 语音端点检测（VAD）
- 语言识别（LID）
- 情感识别（SER）
- 说话人辨别

支持离线音频文件处理和实时音频流处理。
"""

import logging
import os
import tempfile
import time
from typing import Optional, Dict, Any, List
from pathlib import Path

from backend.utils.asr.base_engine import BaseASREngine

logger = logging.getLogger(__name__)


class FunASREngine(BaseASREngine):
    """
    FunASR 引擎实现
    
    支持四大核心功能：
    1. VAD（语音端点检测）- 识别有效语音段
    2. LID（语言识别）- 识别语种并转写文本
    3. SER（情感识别）- 识别语音情感
    4. 说话人辨别 - 区分不同说话人
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化 FunASR 引擎
        
        Args:
            config: 配置字典，包含以下参数：
                - sample_rate: 采样率（默认 16000）
                - channels: 声道数（默认 1）
                - sample_width: 采样位深（默认 2，即 16-bit）
                - device: 设备类型 "cpu" 或 "cuda:0"（默认 "cpu"）
                - language: 语言设置 "auto", "zh", "en" 等（默认 "auto"）
                - min_audio_length: 最小音频长度（秒，默认 1.0）
                - vad_enabled: 是否启用 VAD（默认 True）
                - lid_enabled: 是否启用语言识别（默认 True）
                - ser_enabled: 是否启用情感识别（默认 False）
                - speaker_enabled: 是否启用说话人辨别（默认 False）
                - model_cache_dir: 模型缓存目录（可选）
                - output_dir: 输出目录（默认 "./funasr_output"）
        """
        self.config = config
        
        # 音频参数
        self.sample_rate: int = config.get("sample_rate", 16000)
        self.channels: int = config.get("channels", 1)
        self.sample_width: int = config.get("sample_width", 2)
        self.min_audio_length: float = config.get("min_audio_length", 1.0)
        
        # 设备配置
        self.device: str = config.get("device", "cpu")
        self.language: str = config.get("language", "auto")
        
        # 功能开关
        self.vad_enabled: bool = config.get("vad_enabled", True)
        self.lid_enabled: bool = config.get("lid_enabled", True)
        self.ser_enabled: bool = config.get("ser_enabled", False)
        self.speaker_enabled: bool = config.get("speaker_enabled", False)
        
        # 路径配置
        self.output_dir: str = config.get("output_dir", "./funasr_output")
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 模型缓存配置 - 统一使用 backend/data/asr 目录
        model_cache_dir = config.get("model_cache_dir")
        if model_cache_dir:
            os.environ["MODELSCOPE_CACHE"] = str(model_cache_dir)
            logger.info(f"设置模型缓存目录: {model_cache_dir}")
        
        # 模型实例
        self.vad_model = None
        self.lid_model = None
        self.ser_model = None
        self.speaker_model = None
        
        # 音频缓冲区
        self.audio_buffer = bytearray()
        
        # 统计信息
        self.stats = {
            "total_processed": 0,
            "vad_triggers": 0,
            "transcripts": 0,
            "errors": 0
        }
    
    async def initialize(self) -> bool:
        """
        初始化 FunASR 引擎，加载所需模型
        
        Returns:
            bool: 初始化成功返回 True，失败返回 False
        """
        try:
            # 延迟导入，避免在不需要时加载
            from funasr import AutoModel
            
            logger.info("🚀 正在初始化 FunASR 引擎...")
            logger.info(f"音频配置: {self.sample_rate}Hz, {self.channels}ch, {self.sample_width * 8}bit")
            logger.info(f"设备: {self.device}, 语言: {self.language}")
            
            # 检查模型缓存目录
            model_cache_dir = self.config.get("model_cache_dir")
            if model_cache_dir and not self._check_models_exist(model_cache_dir):
                logger.error(f"❌ 模型文件未找到，请先运行 python backend/all_ready.py 下载模型")
                logger.error(f"预期模型目录: {model_cache_dir}")
                return False
            
            # 1. 加载 VAD 模型
            if self.vad_enabled:
                logger.info("加载 VAD 模型 (fsmn-vad)...")
                start_time = time.time()
                self.vad_model = AutoModel(
                    model="fsmn-vad",
                    device=self.device,
                    disable_update=True
                )
                logger.info(f"✅ VAD 模型加载完成 (耗时 {time.time() - start_time:.2f}秒)")
            
            # 2. 加载语言识别模型（包含 ASR 功能）
            if self.lid_enabled:
                logger.info("加载语言识别模型 (iic/SenseVoiceSmall)...")
                start_time = time.time()
                self.lid_model = AutoModel(
                    model="iic/SenseVoiceSmall",
                    trust_remote_code=True,
                    device=self.device,
                    disable_update=True
                )
                logger.info(f"✅ 语言识别模型加载完成 (耗时 {time.time() - start_time:.2f}秒)")
            
            # 3. 加载情感识别模型（可选）
            if self.ser_enabled:
                # 检查情感识别模型是否存在
                ser_model_path = Path(model_cache_dir) / "models" / "iic" / "emotion2vec_plus_large"
                if not ser_model_path.exists():
                    logger.warning("❌ 情感识别模型未找到，已禁用情感识别功能")
                    logger.warning("如需使用情感识别，请运行: python backend/all_ready.py --download-emotion")
                    self.ser_enabled = False
                else:
                    logger.info("加载情感识别模型 (emotion2vec_plus_large)...")
                    start_time = time.time()
                    self.ser_model = AutoModel(
                        model="emotion2vec_plus_large",
                        device=self.device,
                        disable_update=True
                    )
                    logger.info(f"✅ 情感识别模型加载完成 (耗时 {time.time() - start_time:.2f}秒)")
            
            # 4. 加载说话人辨别模型（可选）
            if self.speaker_enabled:
                # 检查说话人辨别模型是否存在
                speaker_model_path = Path(model_cache_dir) / "models" / "iic" / "speech_campplus_sv_zh-cn_16k-common"
                if not speaker_model_path.exists():
                    logger.warning("❌ 说话人辨别模型未找到，已禁用说话人辨别功能")
                    logger.warning("如需使用说话人辨别，请运行: python backend/all_ready.py --download-speaker")
                    self.speaker_enabled = False
                else:
                    logger.info("加载说话人辨别模型 (speech_campplus_sv_zh-cn_16k-common)...")
                    start_time = time.time()
                    self.speaker_model = AutoModel(
                        model="iic/speech_campplus_sv_zh-cn_16k-common",
                        trust_remote_code=True,
                        device=self.device,
                        disable_update=True
                    )
                    logger.info(f"✅ 说话人辨别模型加载完成 (耗时 {time.time() - start_time:.2f}秒)")
            
            logger.info("✅ FunASR 引擎初始化完成")
            return True
            
        except ImportError as e:
            logger.error(f"❌ FunASR 库未安装: {e}")
            logger.error("请运行: pip install funasr")
            return False
        except Exception as e:
            logger.error(f"❌ FunASR 引擎初始化失败: {e}", exc_info=True)
            return False
    
    async def process_audio(self, audio_data: bytes) -> Optional[str]:
        """
        处理音频数据，进行语音识别
        
        Args:
            audio_data: PCM 音频数据
            
        Returns:
            Optional[str]: 识别出的文本，如果没有识别结果返回 None
        """
        try:
            # 累积音频数据
            self.audio_buffer.extend(audio_data)
            
            # 计算缓冲区时长
            bytes_per_second = self.sample_rate * self.channels * self.sample_width
            buffer_duration = len(self.audio_buffer) / bytes_per_second
            
            # 如果缓冲区未达到最小长度，继续累积
            if buffer_duration < self.min_audio_length:
                return None
            
            # 保存音频到临时文件
            temp_audio_path = self._save_temp_audio(bytes(self.audio_buffer))
            
            # 清空缓冲区
            self.audio_buffer.clear()
            
            # 执行识别
            result = await self._recognize_audio(temp_audio_path)
            
            # 清理临时文件
            try:
                os.remove(temp_audio_path)
            except Exception:
                pass
            
            self.stats["total_processed"] += 1
            if result:
                self.stats["transcripts"] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"处理音频时出错: {e}", exc_info=True)
            self.stats["errors"] += 1
            return None
    
    async def detect_vad(self, audio_data: bytes) -> bool:
        """
        检测语音活动（Voice Activity Detection）
        
        Args:
            audio_data: PCM 音频数据
            
        Returns:
            bool: 检测到语音活动返回 True
        """
        if not self.vad_enabled or not self.vad_model:
            return False
        
        try:
            # 保存音频到临时文件
            temp_audio_path = self._save_temp_audio(audio_data)
            
            # 执行 VAD 检测
            result = self.vad_model.generate(input=temp_audio_path)
            
            # 清理临时文件
            try:
                os.remove(temp_audio_path)
            except Exception:
                pass
            
            # 解析 VAD 结果
            if result and len(result) > 0 and "value" in result[0]:
                vad_segments = result[0]["value"]
                # 如果检测到语音段，返回 True
                if vad_segments and len(vad_segments) > 0:
                    self.stats["vad_triggers"] += 1
                    logger.debug(f"VAD 检测到语音段: {vad_segments}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"VAD 检测时出错: {e}", exc_info=True)
            return False
    
    async def clear_buffer(self):
        """清空内部音频缓冲区（用于打断场景）"""
        self.audio_buffer.clear()
        logger.debug("FunASR 缓冲区已清空")
    
    async def shutdown(self):
        """关闭 ASR 引擎，释放资源"""
        logger.info("正在关闭 FunASR 引擎...")
        
        # 清空缓冲区
        self.audio_buffer.clear()
        
        # 释放模型（Python GC 会处理）
        self.vad_model = None
        self.lid_model = None
        self.ser_model = None
        self.speaker_model = None
        
        # 打印统计信息
        logger.info(f"FunASR 统计: 处理 {self.stats['total_processed']} 次, "
                   f"转录 {self.stats['transcripts']} 次, "
                   f"VAD 触发 {self.stats['vad_triggers']} 次, "
                   f"错误 {self.stats['errors']} 次")
        
        logger.info("✅ FunASR 引擎已关闭")
    
    # ==================== 辅助方法 ====================
    
    def _check_models_exist(self, cache_dir: str) -> bool:
        """
        检查模型是否已下载
        
        Args:
            cache_dir: 模型缓存目录
            
        Returns:
            bool: 模型存在返回 True
        """
        cache_path = Path(cache_dir)
        if not cache_path.exists():
            logger.warning(f"缓存目录不存在: {cache_path}")
            return False
        
        # FunASR 使用 models 目录结构
        models_dir = cache_path / "models"
        if not models_dir.exists():
            logger.warning(f"models 目录不存在: {models_dir}")
            return False
        
        # 检查必需的模型（根据配置）
        required_models = []
        optional_models = []
        
        # VAD 模型（如果启用）
        if self.vad_enabled:
            required_models.append("iic/speech_fsmn_vad_zh-cn-16k-common-pytorch")
        
        # 语言识别模型（如果启用）
        if self.lid_enabled:
            required_models.append("iic/SenseVoiceSmall")
        
        # 情感识别模型（可选）
        if self.ser_enabled:
            optional_models.append("iic/emotion2vec_plus_large")
        
        # 说话人辨别模型（可选）
        if self.speaker_enabled:
            optional_models.append("iic/speech_campplus_sv_zh-cn_16k-common")
        
        # 检查必需模型
        found_count = 0
        missing_models = []
        for model_id in required_models:
            parts = model_id.split("/")
            model_path = models_dir / parts[0] / parts[1]
            if model_path.exists():
                found_count += 1
                logger.debug(f"✓ 找到模型: {model_id}")
            else:
                logger.warning(f"✗ 缺失必需模型: {model_id} (路径: {model_path})")
                missing_models.append(model_id)
        
        # 检查可选模型
        for model_id in optional_models:
            parts = model_id.split("/")
            model_path = models_dir / parts[0] / parts[1]
            if model_path.exists():
                logger.debug(f"✓ 找到可选模型: {model_id}")
            else:
                logger.warning(f"✗ 缺失可选模型: {model_id} (路径: {model_path})")
                missing_models.append(model_id)
        
        if found_count == len(required_models):
            logger.info(f"✅ 找到所有必需模型 ({found_count}/{len(required_models)})")
            if missing_models:
                logger.warning(f"缺失可选模型: {', '.join(missing_models)}")
            return True
        else:
            logger.error(f"❌ 缺失必需模型 ({found_count}/{len(required_models)})")
            logger.error(f"缺失的模型: {', '.join(missing_models)}")
            return False
    
    def _save_temp_audio(self, audio_data: bytes) -> str:
        """
        将音频数据保存为临时 WAV 文件
        
        Args:
            audio_data: PCM 音频数据
            
        Returns:
            str: 临时文件路径
        """
        import wave
        
        # 创建临时文件
        fd, temp_path = tempfile.mkstemp(suffix=".wav", dir=self.output_dir)
        os.close(fd)
        
        # 写入 WAV 文件
        with wave.open(temp_path, 'wb') as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(self.sample_width)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio_data)
        
        return temp_path
    
    async def _recognize_audio(self, audio_path: str) -> Optional[str]:
        """
        对音频文件进行完整识别（包括 LID、SER、说话人辨别）
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            Optional[str]: 识别结果文本
        """
        result_text = None
        
        try:
            # 1. 语言识别 + 语音转写（主要功能）
            if self.lid_enabled and self.lid_model:
                lid_result = self._recognize_language(audio_path)
                if lid_result["status"] == "success":
                    data = lid_result["data"]
                    language = data.get("language", "unknown")
                    text = data.get("text", "")
                    
                    if text:
                        result_text = text
                        logger.info(f"识别结果 [{language}]: {text}")
            
            # 2. 情感识别（可选）
            if self.ser_enabled and self.ser_model and result_text:
                ser_result = self._recognize_emotion(audio_path)
                if ser_result["status"] == "success":
                    emotion = ser_result["data"].get("emotion", "unknown")
                    confidence = ser_result["data"].get("confidence", 0.0)
                    logger.info(f"情感识别: {emotion} (置信度: {confidence:.2f})")
            
            # 3. 说话人辨别（可选）
            if self.speaker_enabled and self.speaker_model:
                speaker_result = self._diarize_speakers(audio_path)
                if speaker_result["status"] == "success":
                    speakers = speaker_result["data"]
                    logger.info(f"说话人数量: {len(set(s['speaker'] for s in speakers))}")
            
            return result_text
            
        except Exception as e:
            logger.error(f"识别音频时出错: {e}", exc_info=True)
            return None
    
    def _recognize_language(self, audio_path: str) -> dict:
        """
        语言识别 + 语音转写
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            dict: 结构化结果
        """
        try:
            result = self.lid_model.generate(
                input=audio_path,
                language=self.language,
                use_itn=True  # 文本规范化
            )
            
            lid_data = {
                "language": result[0].get("language", "unknown"),
                "text": result[0].get("text", "")
            }
            
            return {
                "status": "success",
                "data": lid_data,
                "msg": ""
            }
        except Exception as e:
            return {
                "status": "fail",
                "data": {},
                "msg": f"语种识别失败: {str(e)}"
            }
    
    def _recognize_emotion(self, audio_path: str) -> dict:
        """
        情感识别
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            dict: 结构化结果
        """
        try:
            result = self.ser_model.generate(
                input=audio_path,
                output_dir=self.output_dir,
                granularity="utterance",  # 整句级别
                extract_embedding=False
            )
            
            ser_data = {
                "emotion": result[0].get("emotion", "unknown"),
                "confidence": result[0].get("scores", 0.0)
            }
            
            return {
                "status": "success",
                "data": ser_data,
                "msg": ""
            }
        except Exception as e:
            return {
                "status": "fail",
                "data": {},
                "msg": f"情感识别失败: {str(e)}"
            }
    
    def _diarize_speakers(self, audio_path: str) -> dict:
        """
        说话人辨别
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            dict: 结构化结果
        """
        try:
            result = self.speaker_model.generate(input=audio_path)
            
            speaker_data = []
            for item in result[0].get("value", []):
                speaker_data.append({
                    "speaker": item.get("spk", "unknown"),
                    "text": item.get("text", ""),
                    "start_time": item.get("start", 0),
                    "end_time": item.get("end", 0)
                })
            
            return {
                "status": "success",
                "data": speaker_data,
                "msg": ""
            }
        except Exception as e:
            return {
                "status": "fail",
                "data": [],
                "msg": f"说话人辨别失败: {str(e)}"
            }
    
    # ==================== 独立功能接口 ====================
    
    async def vad_detect_file(self, audio_path: str) -> dict:
        """
        对音频文件进行 VAD 检测
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            dict: VAD 检测结果
        """
        if not self.vad_model:
            return {"status": "fail", "data": [], "msg": "VAD 模型未加载"}
        
        try:
            result = self.vad_model.generate(input=audio_path)
            vad_segments = result[0].get("value", []) if result else []
            
            return {
                "status": "success",
                "data": vad_segments,
                "msg": ""
            }
        except Exception as e:
            return {
                "status": "fail",
                "data": [],
                "msg": f"VAD 检测失败: {str(e)}"
            }
    
    async def recognize_file(self, audio_path: str) -> dict:
        """
        对音频文件进行完整识别（LID + SER + 说话人）
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            dict: 完整识别结果
        """
        results = {}
        
        # VAD 检测
        if self.vad_enabled:
            results["vad"] = await self.vad_detect_file(audio_path)
        
        # 语言识别
        if self.lid_enabled and self.lid_model:
            results["lid"] = self._recognize_language(audio_path)
        
        # 情感识别
        if self.ser_enabled and self.ser_model:
            results["ser"] = self._recognize_emotion(audio_path)
        
        # 说话人辨别
        if self.speaker_enabled and self.speaker_model:
            results["speaker"] = self._diarize_speakers(audio_path)
        
        return results
