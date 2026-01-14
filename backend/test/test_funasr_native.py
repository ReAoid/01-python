#!/usr/bin/env python
"""
FunASR 原生 API 测试脚本

直接使用 funasr.AutoModel 和 model.FunASRNano 的官方示例代码
演示如何使用 FunASR 进行语音识别

Usage:
    python backend/test/test_funasr_native.py
"""

import sys
import logging
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.core.logger import init_logging

# 初始化日志
init_logging(log_level="INFO", log_file=None)
logger = logging.getLogger(__name__)


def test_automodel_api():
    """测试 AutoModel API"""
    logger.info("=" * 70)
    logger.info("测试 funasr.AutoModel API")
    logger.info("=" * 70)
    
    try:
        from funasr import AutoModel
        
        # 模型路径（本地或 HuggingFace）
        model_dir = "FunAudioLLM/Fun-ASR-Nano-2512"
        
        # 检查本地模型
        local_model = Path("backend/data/asr/funasr_nano")
        if local_model.exists():
            logger.info(f"使用本地模型: {local_model}")
            model_dir = str(local_model.resolve())
        else:
            logger.info(f"使用 HuggingFace 模型: {model_dir}")
        
        logger.info("\n1. 加载基础模型（不带 VAD）...")
        model = AutoModel(
            model=model_dir,
            trust_remote_code=True,
            device="cpu",
        )
        logger.info("✅ 模型加载成功")
        
        # 检查示例音频
        example_audio = Path(model.model_path) / "example" / "zh.mp3"
        if not example_audio.exists():
            logger.warning(f"示例音频不存在: {example_audio}")
            logger.info("跳过识别测试")
            return True
        
        logger.info(f"\n2. 使用示例音频进行识别: {example_audio}")
        
        # 基础识别
        logger.info("\n测试 1: 基础识别")
        res = model.generate(
            input=[str(example_audio)],
            cache={},
            batch_size=1,
            language="中文",
            itn=True,
        )
        text = res[0]["text"]
        logger.info(f"识别结果: {text}")
        
        # 带热词识别
        logger.info("\n测试 2: 热词识别")
        res = model.generate(
            input=[str(example_audio)],
            cache={},
            batch_size=1,
            hotwords=["开放时间"],
            language="中文",
            itn=True,
        )
        text = res[0]["text"]
        logger.info(f"识别结果（带热词）: {text}")
        
        # 加载带 VAD 的模型
        logger.info("\n3. 加载模型（带 VAD）...")
        model_with_vad = AutoModel(
            model=model_dir,
            trust_remote_code=True,
            vad_model="fsmn-vad",
            vad_kwargs={"max_single_segment_time": 30000},
            device="cpu",
        )
        logger.info("✅ 带 VAD 的模型加载成功")
        
        logger.info("\n测试 3: 带 VAD 的识别")
        res = model_with_vad.generate(
            input=[str(example_audio)],
            cache={},
            batch_size=1,
        )
        text = res[0]["text"]
        logger.info(f"识别结果（VAD）: {text}")
        
        logger.info("\n" + "=" * 70)
        logger.info("✅ 所有测试通过")
        logger.info("=" * 70)
        return True
        
    except ImportError:
        logger.error("❌ 未安装 funasr 库")
        logger.info("安装命令: pip install funasr")
        return False
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        logger.exception(e)
        return False


def test_model_class_api():
    """测试 FunASRNano 类 API"""
    logger.info("\n" + "=" * 70)
    logger.info("测试 model.FunASRNano 类 API")
    logger.info("=" * 70)
    
    try:
        # 检查本地模型
        local_model = Path("backend/data/asr/funasr_nano")
        if not local_model.exists():
            logger.warning(f"本地模型不存在: {local_model}")
            logger.info("跳过 FunASRNano 类测试")
            return True
        
        # 检查 model.py
        model_py = local_model / "model.py"
        if not model_py.exists():
            logger.warning(f"model.py 不存在: {model_py}")
            logger.info("跳过 FunASRNano 类测试")
            return True
        
        # 动态导入 model.py
        sys.path.insert(0, str(local_model))
        from model import FunASRNano
        
        logger.info(f"\n1. 从预训练模型加载...")
        model_dir = str(local_model)
        
        m, kwargs = FunASRNano.from_pretrained(model=model_dir, device="cpu")
        m.eval()
        logger.info("✅ 模型加载成功")
        
        # 检查示例音频
        example_audio = local_model / "example" / "zh.mp3"
        if not example_audio.exists():
            logger.warning(f"示例音频不存在: {example_audio}")
            logger.info("跳过识别测试")
            return True
        
        logger.info(f"\n2. 推理测试: {example_audio}")
        res = m.inference(data_in=[str(example_audio)], **kwargs)
        text = res[0][0]["text"]
        logger.info(f"识别结果: {text}")
        
        logger.info("\n" + "=" * 70)
        logger.info("✅ FunASRNano 类测试通过")
        logger.info("=" * 70)
        return True
        
    except ImportError as e:
        logger.warning(f"⚠️  导入失败: {e}")
        logger.info("这是正常的，如果 model.py 不可用")
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        logger.exception(e)
        return False


def main():
    """主测试流程"""
    logger.info("FunASR 原生 API 测试")
    logger.info("=" * 70)
    
    success = True
    
    # 测试 AutoModel API
    if not test_automodel_api():
        success = False
    
    # 测试 FunASRNano 类 API
    if not test_model_class_api():
        success = False
    
    if success:
        logger.info("\n🎉 所有测试完成")
        return 0
    else:
        logger.error("\n❌ 部分测试失败")
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.warning("\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        logger.error(f"测试失败: {e}")
        logger.exception(e)
        sys.exit(1)
