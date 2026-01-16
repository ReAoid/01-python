"""
FunASR 引擎测试文件

测试 FunASR 引擎的各项功能：
1. 基本初始化和配置
2. VAD 语音端点检测
3. 语言识别和语音转写
4. 情感识别（可选）
5. 说话人辨别（可选）
6. 实时音频流处理

使用方法：
    python test_funasr.py
"""

import asyncio
import logging
import sys
import os
import wave
import struct
import math
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.utils.asr.funasr_engine import FunASREngine

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_test_audio(duration: float = 2.0, frequency: int = 440, 
                       sample_rate: int = 16000, output_path: str = None) -> str:
    """
    生成测试音频文件（正弦波）
    
    Args:
        duration: 音频时长（秒）
        frequency: 音频频率（Hz）
        sample_rate: 采样率
        output_path: 输出文件路径
        
    Returns:
        str: 生成的音频文件路径
    """
    if output_path is None:
        output_path = "test_audio.wav"
    
    # 生成正弦波数据
    num_samples = int(duration * sample_rate)
    audio_data = []
    
    for i in range(num_samples):
        # 生成正弦波样本（16-bit PCM）
        sample = int(32767 * 0.3 * math.sin(2 * math.pi * frequency * i / sample_rate))
        audio_data.append(sample)
    
    # 写入 WAV 文件
    with wave.open(output_path, 'wb') as wav_file:
        wav_file.setnchannels(1)  # 单声道
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(struct.pack(f'<{len(audio_data)}h', *audio_data))
    
    logger.info(f"✅ 生成测试音频: {output_path} ({duration}秒, {frequency}Hz)")
    return output_path


async def test_basic_initialization():
    """测试基本初始化"""
    logger.info("\n" + "="*60)
    logger.info("测试 1: 基本初始化")
    logger.info("="*60)
    
    # 设置模型缓存目录
    backend_dir = Path(__file__).parent.parent
    model_cache_dir = backend_dir / "data" / "asr"
    
    config = {
        "sample_rate": 16000,
        "channels": 1,
        "sample_width": 2,
        "device": "cpu",
        "language": "auto",
        "vad_enabled": True,
        "lid_enabled": True,
        "ser_enabled": False,
        "speaker_enabled": False,
        "model_cache_dir": str(model_cache_dir),
        "output_dir": "./test_output"
    }
    
    engine = FunASREngine(config)
    
    # 初始化引擎
    success = await engine.initialize()
    
    if success:
        logger.info("✅ 初始化成功")
        await engine.shutdown()
        return True
    else:
        logger.error("❌ 初始化失败")
        return False


async def test_vad_detection():
    """测试 VAD 语音端点检测"""
    logger.info("\n" + "="*60)
    logger.info("测试 2: VAD 语音端点检测")
    logger.info("="*60)
    
    # 设置模型缓存目录
    backend_dir = Path(__file__).parent.parent
    model_cache_dir = backend_dir / "data" / "asr"
    
    config = {
        "sample_rate": 16000,
        "channels": 1,
        "sample_width": 2,
        "device": "cpu",
        "vad_enabled": True,
        "lid_enabled": False,
        "model_cache_dir": str(model_cache_dir),
        "output_dir": "./test_output"
    }
    
    engine = FunASREngine(config)
    
    if not await engine.initialize():
        logger.error("❌ 引擎初始化失败")
        return False
    
    try:
        # 生成测试音频
        test_audio = generate_test_audio(duration=1.0, frequency=440)
        
        # 读取音频数据
        with wave.open(test_audio, 'rb') as wav_file:
            audio_data = wav_file.readframes(wav_file.getnframes())
        
        # 执行 VAD 检测
        logger.info("执行 VAD 检测...")
        is_speech = await engine.detect_vad(audio_data)
        
        logger.info(f"VAD 检测结果: {'检测到语音' if is_speech else '未检测到语音'}")
        
        # 测试文件级 VAD
        vad_result = await engine.vad_detect_file(test_audio)
        logger.info(f"文件级 VAD 结果: {vad_result}")
        
        # 清理
        os.remove(test_audio)
        await engine.shutdown()
        
        logger.info("✅ VAD 测试完成")
        return True
        
    except Exception as e:
        logger.error(f"❌ VAD 测试失败: {e}", exc_info=True)
        await engine.shutdown()
        return False


async def test_language_recognition():
    """测试语言识别和语音转写"""
    logger.info("\n" + "="*60)
    logger.info("测试 3: 语言识别和语音转写")
    logger.info("="*60)
    
    # 设置模型缓存目录
    backend_dir = Path(__file__).parent.parent
    model_cache_dir = backend_dir / "data" / "asr"
    
    config = {
        "sample_rate": 16000,
        "channels": 1,
        "sample_width": 2,
        "device": "cpu",
        "language": "auto",
        "vad_enabled": False,
        "lid_enabled": True,
        "model_cache_dir": str(model_cache_dir),
        "output_dir": "./test_output"
    }
    
    engine = FunASREngine(config)
    
    if not await engine.initialize():
        logger.error("❌ 引擎初始化失败")
        return False
    
    try:
        # 生成测试音频
        test_audio = generate_test_audio(duration=2.0, frequency=440)
        
        logger.info("执行语言识别...")
        result = engine._recognize_language(test_audio)
        
        logger.info(f"识别结果: {result}")
        
        if result["status"] == "success":
            logger.info(f"语种: {result['data']['language']}")
            logger.info(f"文本: {result['data']['text']}")
        
        # 清理
        os.remove(test_audio)
        await engine.shutdown()
        
        logger.info("✅ 语言识别测试完成")
        return True
        
    except Exception as e:
        logger.error(f"❌ 语言识别测试失败: {e}", exc_info=True)
        await engine.shutdown()
        return False


async def test_stream_processing():
    """测试实时音频流处理"""
    logger.info("\n" + "="*60)
    logger.info("测试 4: 实时音频流处理")
    logger.info("="*60)
    
    # 设置模型缓存目录
    backend_dir = Path(__file__).parent.parent
    model_cache_dir = backend_dir / "data" / "asr"
    
    config = {
        "sample_rate": 16000,
        "channels": 1,
        "sample_width": 2,
        "device": "cpu",
        "language": "auto",
        "min_audio_length": 1.0,  # 1秒触发识别
        "vad_enabled": True,
        "lid_enabled": True,
        "model_cache_dir": str(model_cache_dir),
        "output_dir": "./test_output"
    }
    
    engine = FunASREngine(config)
    
    if not await engine.initialize():
        logger.error("❌ 引擎初始化失败")
        return False
    
    try:
        # 生成测试音频
        test_audio = generate_test_audio(duration=3.0, frequency=440)
        
        # 读取音频数据
        with wave.open(test_audio, 'rb') as wav_file:
            audio_data = wav_file.readframes(wav_file.getnframes())
        
        # 模拟流式处理：分块发送
        chunk_size = 16000 * 2  # 0.5秒的数据
        total_chunks = len(audio_data) // chunk_size
        
        logger.info(f"开始流式处理 ({total_chunks} 个数据块)...")
        
        for i in range(total_chunks):
            start = i * chunk_size
            end = start + chunk_size
            chunk = audio_data[start:end]
            
            # 处理音频块
            result = await engine.process_audio(chunk)
            
            if result:
                logger.info(f"📝 识别结果 (块 {i+1}): {result}")
        
        # 清理
        os.remove(test_audio)
        await engine.shutdown()
        
        logger.info("✅ 流式处理测试完成")
        return True
        
    except Exception as e:
        logger.error(f"❌ 流式处理测试失败: {e}", exc_info=True)
        await engine.shutdown()
        return False


async def test_full_features():
    """测试完整功能（VAD + LID，可选 SER + 说话人）"""
    logger.info("\n" + "="*60)
    logger.info("测试 5: 完整功能测试")
    logger.info("="*60)
    
    # 设置模型缓存目录
    backend_dir = Path(__file__).parent.parent
    model_cache_dir = backend_dir / "data" / "asr"
    
    # 检查可选模型是否存在
    emotion_model_exists = (model_cache_dir / "models" / "iic" / "emotion2vec_plus_large").exists()
    speaker_model_exists = (model_cache_dir / "models" / "iic" / "speech_campplus_sv_zh-cn_16k-common").exists()
    
    if emotion_model_exists:
        logger.info("✓ 检测到情感识别模型，将启用情感识别")
    else:
        logger.warning("⚠️  情感识别模型未安装，跳过情感识别测试")
        logger.info("提示: 使用 python backend/all_ready.py --download-emotion 下载")
    
    if speaker_model_exists:
        logger.info("✓ 检测到说话人辨别模型，将启用说话人辨别")
    else:
        logger.warning("⚠️  说话人辨别模型未安装，跳过说话人辨别测试")
        logger.info("提示: 使用 python backend/all_ready.py --download-speaker 下载")
    
    config = {
        "sample_rate": 16000,
        "channels": 1,
        "sample_width": 2,
        "device": "cpu",
        "language": "auto",
        "vad_enabled": True,
        "lid_enabled": True,
        "ser_enabled": emotion_model_exists,  # 仅在模型存在时启用
        "speaker_enabled": speaker_model_exists,  # 仅在模型存在时启用
        "model_cache_dir": str(model_cache_dir),
        "output_dir": "./test_output"
    }
    
    engine = FunASREngine(config)
    
    if not await engine.initialize():
        logger.error("❌ 引擎初始化失败")
        return False
    
    try:
        # 生成测试音频
        test_audio = generate_test_audio(duration=2.0, frequency=440)
        
        logger.info("执行完整功能识别...")
        results = await engine.recognize_file(test_audio)
        
        logger.info("识别结果:")
        for feature, result in results.items():
            logger.info(f"  {feature}: {result}")
        
        # 清理
        os.remove(test_audio)
        await engine.shutdown()
        
        logger.info("✅ 完整功能测试完成")
        return True
        
    except Exception as e:
        logger.error(f"❌ 完整功能测试失败: {e}", exc_info=True)
        await engine.shutdown()
        return False


async def test_with_real_audio():
    """使用真实音频文件测试（如果存在）"""
    logger.info("\n" + "="*60)
    logger.info("测试 6: 真实音频文件测试")
    logger.info("="*60)
    
    # 查找测试音频文件
    test_files = [
        "test_audio.wav",
        "test_output.wav",
        "../test/test_output.wav"
    ]
    
    audio_file = None
    for f in test_files:
        if os.path.exists(f):
            audio_file = f
            break
    
    if not audio_file:
        logger.warning("⚠️  未找到真实音频文件，跳过此测试")
        logger.info("提示: 可以将音频文件命名为 test_audio.wav 放在当前目录")
        return True
    
    logger.info(f"使用音频文件: {audio_file}")
    
    # 设置模型缓存目录
    backend_dir = Path(__file__).parent.parent
    model_cache_dir = backend_dir / "data" / "asr"
    
    config = {
        "sample_rate": 16000,
        "channels": 1,
        "sample_width": 2,
        "device": "cpu",
        "language": "auto",
        "vad_enabled": True,
        "lid_enabled": True,
        "ser_enabled": False,
        "speaker_enabled": False,
        "model_cache_dir": str(model_cache_dir),
        "output_dir": "./test_output"
    }
    
    engine = FunASREngine(config)
    
    if not await engine.initialize():
        logger.error("❌ 引擎初始化失败")
        return False
    
    try:
        logger.info("执行识别...")
        results = await engine.recognize_file(audio_file)
        
        logger.info("\n识别结果:")
        logger.info("="*60)
        for feature, result in results.items():
            logger.info(f"\n{feature.upper()}:")
            if isinstance(result, dict):
                for key, value in result.items():
                    logger.info(f"  {key}: {value}")
            else:
                logger.info(f"  {result}")
        logger.info("="*60)
        
        await engine.shutdown()
        
        logger.info("✅ 真实音频测试完成")
        return True
        
    except Exception as e:
        logger.error(f"❌ 真实音频测试失败: {e}", exc_info=True)
        await engine.shutdown()
        return False


async def main():
    """主测试函数"""
    logger.info("🚀 开始 FunASR 引擎测试")
    logger.info("="*60)
    
    # 创建输出目录
    os.makedirs("./test_output", exist_ok=True)
    
    # 运行测试
    tests = [
        ("基本初始化", test_basic_initialization),
        ("VAD 检测", test_vad_detection),
        ("语言识别", test_language_recognition),
        ("流式处理", test_stream_processing),
        ("完整功能", test_full_features),
        ("真实音频", test_with_real_audio),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"测试 '{test_name}' 异常: {e}", exc_info=True)
            results.append((test_name, False))
    
    # 打印测试总结
    logger.info("\n" + "="*60)
    logger.info("测试总结")
    logger.info("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        logger.info(f"{test_name}: {status}")
    
    logger.info("="*60)
    logger.info(f"总计: {passed}/{total} 通过")
    
    if passed == total:
        logger.info("🎉 所有测试通过！")
    else:
        logger.warning(f"⚠️  {total - passed} 个测试失败")
    
    return passed == total


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        logger.error(f"测试过程中发生错误: {e}", exc_info=True)
        sys.exit(1)
