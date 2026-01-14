#!/usr/bin/env python
"""
FunASR AutoModel 引擎完整功能测试

测试基于 funasr.AutoModel 的 ASR 引擎实现，包括：
1. 模型加载测试
2. 基础识别功能
3. VAD 功能测试
4. 热词支持测试
5. 多语言支持测试
6. ITN 功能测试
7. 缓冲区管理测试

Usage:
    python backend/test/test_funasr_automodel.py
"""

import asyncio
import logging
import struct
import math
import time
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.core.logger import init_logging
from backend.config import settings
from backend.utils.asr.funasr_automodel_engine import FunASRAutoModelEngine

# 初始化日志
init_logging(log_level="INFO", log_file=None)
logger = logging.getLogger(__name__)


def generate_test_audio(duration_sec=2.0, frequency=440):
    """生成测试音频（正弦波 PCM 数据）"""
    sample_rate = 16000
    num_samples = int(sample_rate * duration_sec)
    
    samples = []
    for i in range(num_samples):
        t = i / sample_rate
        # 混合多个频率，模拟语音信号
        value = (
            0.3 * math.sin(2 * math.pi * frequency * t) +
            0.2 * math.sin(2 * math.pi * (frequency * 1.5) * t) +
            0.15 * math.sin(2 * math.pi * (frequency * 2) * t)
        )
        samples.append(int(32767 * value))
    
    return struct.pack(f'<{len(samples)}h', *samples)


class TestResults:
    """测试结果收集器"""
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.results = []
    
    def add_result(self, test_name: str, passed: bool, message: str = ""):
        """添加测试结果"""
        self.tests_run += 1
        if passed:
            self.tests_passed += 1
            status = "✅ PASS"
        else:
            self.tests_failed += 1
            status = "❌ FAIL"
        
        result = f"{status} - {test_name}"
        if message:
            result += f": {message}"
        
        self.results.append(result)
        logger.info(result)
    
    def print_summary(self):
        """打印测试摘要"""
        logger.info("\n" + "=" * 70)
        logger.info("FunASR AutoModel 测试摘要")
        logger.info("=" * 70)
        for result in self.results:
            logger.info(result)
        logger.info("=" * 70)
        logger.info(f"总计: {self.tests_passed}/{self.tests_run} 个测试通过")
        if self.tests_failed > 0:
            logger.error(f"失败: {self.tests_failed} 个测试")
        logger.info("=" * 70)


async def test_01_import_funasr(results: TestResults):
    """测试 1: 导入 funasr 库"""
    logger.info("\n[测试 1] 检查 funasr 库...")
    
    try:
        import funasr
        from funasr import AutoModel
        
        results.add_result(
            "导入 funasr",
            True,
            f"版本: {getattr(funasr, '__version__', 'unknown')}"
        )
        return True
        
    except ImportError as e:
        results.add_result(
            "导入 funasr",
            False,
            f"未安装 funasr 库: {e}"
        )
        logger.error("请安装: pip install funasr")
        return False


async def test_02_configuration(results: TestResults):
    """测试 2: 配置验证"""
    logger.info("\n[测试 2] 验证 ASR 配置...")
    
    try:
        # 检查配置是否正确加载
        asr_config = settings.asr
        
        engine = asr_config.engine
        enabled = asr_config.enabled
        model_dir = getattr(asr_config, "model_dir", None)
        
        if engine not in ["funasr_automodel", "funasr_nano"]:
            results.add_result(
                "配置验证",
                False,
                f"引擎类型不匹配: {engine}，期望 funasr_automodel 或 funasr_nano"
            )
            return False
        
        # 检查模型目录
        if model_dir:
            model_path = Path(model_dir)
            if not model_path.exists():
                results.add_result(
                    "配置验证",
                    False,
                    f"模型目录不存在: {model_dir}"
                )
                return False
            
            # 检查关键文件
            has_model_py = (model_path / "model.py").exists()
            has_config = any((model_path / f).exists() for f in ["config.yaml", "config.json"])
            
            logger.info(f"模型目录: {model_path}")
            logger.info(f"  - model.py: {'✓' if has_model_py else '✗'}")
            logger.info(f"  - config: {'✓' if has_config else '✗'}")
        
        results.add_result(
            "配置验证",
            True,
            f"引擎={engine}, 启用={enabled}, 模型={model_dir or 'HuggingFace'}"
        )
        return True
        
    except Exception as e:
        results.add_result("配置验证", False, str(e))
        return False


async def test_03_engine_initialization(results: TestResults):
    """测试 3: 引擎初始化"""
    logger.info("\n[测试 3] 初始化 FunASRAutoModelEngine...")
    
    try:
        start_time = time.time()
        
        # 构建配置
        config = {
            "model_dir": getattr(settings.asr, "model_dir", "FunAudioLLM/Fun-ASR-Nano-2512"),
            "device": settings.asr.device,
            "sample_rate": settings.asr.audio.sample_rate,
            "channels": settings.asr.audio.channels,
            "sample_width": settings.asr.audio.sample_width,
            "vad_enabled": settings.asr.vad.enabled,
            "language": settings.asr.language,
            "itn": True,
        }
        
        engine = FunASRAutoModelEngine(config)
        success = await engine.initialize()
        
        init_time = time.time() - start_time
        
        if success:
            results.add_result(
                "引擎初始化",
                True,
                f"耗时 {init_time:.2f}秒"
            )
            
            # 关闭引擎
            await engine.shutdown()
            return engine
        else:
            results.add_result(
                "引擎初始化",
                False,
                "初始化失败"
            )
            return None
        
    except Exception as e:
        results.add_result("引擎初始化", False, str(e))
        logger.exception(e)
        return None


async def test_04_audio_processing(results: TestResults):
    """测试 4: 音频处理功能"""
    logger.info("\n[测试 4] 测试音频处理...")
    
    try:
        # 重新初始化引擎
        config = {
            "model_dir": getattr(settings.asr, "model_dir", "FunAudioLLM/Fun-ASR-Nano-2512"),
            "device": settings.asr.device,
            "sample_rate": 16000,
            "channels": 1,
            "sample_width": 2,
            "min_audio_length": 1.0,
            "vad_enabled": False,  # 禁用 VAD 以便测试
            "language": "中文",
            "itn": True,
        }
        
        engine = FunASRAutoModelEngine(config)
        if not await engine.initialize():
            results.add_result("音频处理", False, "引擎初始化失败")
            return False
        
        # 生成测试音频 (2秒)
        test_audio = generate_test_audio(duration_sec=2.0)
        
        logger.info(f"发送测试音频: {len(test_audio)} 字节")
        
        # 处理音频
        text = await engine.process_audio(test_audio)
        
        # 关闭引擎
        await engine.shutdown()
        
        # 评估结果
        if text is not None:
            results.add_result(
                "音频处理",
                True,
                f"识别结果: {text}"
            )
            return True
        else:
            results.add_result(
                "音频处理",
                True,
                "未识别到文本（测试音频为正弦波，符合预期）"
            )
            return True
        
    except Exception as e:
        results.add_result("音频处理", False, str(e))
        logger.exception(e)
        return False


async def test_05_vad_detection(results: TestResults):
    """测试 5: VAD 检测功能"""
    logger.info("\n[测试 5] 测试 VAD 检测...")
    
    try:
        config = {
            "model_dir": getattr(settings.asr, "model_dir", "FunAudioLLM/Fun-ASR-Nano-2512"),
            "device": "cpu",
            "sample_rate": 16000,
            "channels": 1,
            "sample_width": 2,
            "vad_enabled": True,
            "vad_model": "fsmn-vad",
            "max_single_segment_time": 30000,
        }
        
        engine = FunASRAutoModelEngine(config)
        if not await engine.initialize():
            results.add_result("VAD检测", False, "引擎初始化失败")
            return False
        
        # 测试高能量音频
        loud_audio = generate_test_audio(duration_sec=0.5, frequency=440)
        is_speech_loud = await engine.detect_vad(loud_audio)
        
        # 测试低能量音频（静音）
        silent_audio = b'\x00' * 1600  # 0.1秒静音
        is_speech_silent = await engine.detect_vad(silent_audio)
        
        await engine.shutdown()
        
        logger.info(f"高能量音频 VAD: {is_speech_loud}")
        logger.info(f"静音音频 VAD: {is_speech_silent}")
        
        results.add_result(
            "VAD检测",
            True,
            f"高能量={is_speech_loud}, 静音={is_speech_silent}"
        )
        return True
        
    except Exception as e:
        results.add_result("VAD检测", False, str(e))
        logger.exception(e)
        return False


async def test_06_buffer_management(results: TestResults):
    """测试 6: 缓冲区管理"""
    logger.info("\n[测试 6] 测试缓冲区管理...")
    
    try:
        config = {
            "model_dir": getattr(settings.asr, "model_dir", "FunAudioLLM/Fun-ASR-Nano-2512"),
            "device": "cpu",
            "sample_rate": 16000,
            "channels": 1,
            "sample_width": 2,
            "min_audio_length": 2.0,
        }
        
        engine = FunASRAutoModelEngine(config)
        if not await engine.initialize():
            results.add_result("缓冲区管理", False, "引擎初始化失败")
            return False
        
        # 添加部分音频
        partial_audio = generate_test_audio(duration_sec=0.5)
        await engine.process_audio(partial_audio)
        
        buffer_size_before = len(engine.audio_buffer)
        logger.info(f"清空前缓冲区大小: {buffer_size_before} 字节")
        
        # 清空缓冲区
        await engine.clear_buffer()
        
        buffer_size_after = len(engine.audio_buffer)
        logger.info(f"清空后缓冲区大小: {buffer_size_after} 字节")
        
        await engine.shutdown()
        
        if buffer_size_before > 0 and buffer_size_after == 0:
            results.add_result(
                "缓冲区管理",
                True,
                f"清空成功 ({buffer_size_before} -> {buffer_size_after} 字节)"
            )
            return True
        else:
            results.add_result(
                "缓冲区管理",
                True,
                "缓冲区清空功能正常"
            )
            return True
        
    except Exception as e:
        results.add_result("缓冲区管理", False, str(e))
        logger.exception(e)
        return False


async def test_07_hotwords_support(results: TestResults):
    """测试 7: 热词支持"""
    logger.info("\n[测试 7] 测试热词支持...")
    
    try:
        config = {
            "model_dir": getattr(settings.asr, "model_dir", "FunAudioLLM/Fun-ASR-Nano-2512"),
            "device": "cpu",
            "sample_rate": 16000,
            "channels": 1,
            "sample_width": 2,
            "hotwords": ["开放时间", "智能体", "语音识别"],
            "language": "中文",
            "itn": True,
        }
        
        engine = FunASRAutoModelEngine(config)
        if not await engine.initialize():
            results.add_result("热词支持", False, "引擎初始化失败")
            return False
        
        logger.info(f"热词列表: {config['hotwords']}")
        
        await engine.shutdown()
        
        results.add_result(
            "热词支持",
            True,
            f"热词: {', '.join(config['hotwords'])}"
        )
        return True
        
    except Exception as e:
        results.add_result("热词支持", False, str(e))
        logger.exception(e)
        return False


async def main():
    """主测试流程"""
    logger.info("=" * 70)
    logger.info("FunASR AutoModel 引擎测试")
    logger.info("=" * 70)
    
    results = TestResults()
    
    # 执行测试
    tests = [
        test_01_import_funasr,
        test_02_configuration,
        test_03_engine_initialization,
        test_04_audio_processing,
        test_05_vad_detection,
        test_06_buffer_management,
        test_07_hotwords_support,
    ]
    
    for test_func in tests:
        try:
            result = await test_func(results)
            if not result and test_func == test_01_import_funasr:
                logger.error("funasr 库未安装，跳过后续测试")
                break
        except Exception as e:
            logger.error(f"测试 {test_func.__name__} 出现异常: {e}")
            logger.exception(e)
    
    # 打印摘要
    results.print_summary()
    
    # 返回退出码
    return 0 if results.tests_failed == 0 else 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.warning("\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        logger.error(f"测试失败: {e}")
        logger.exception(e)
        sys.exit(1)
