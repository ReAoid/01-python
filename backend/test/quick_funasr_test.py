#!/usr/bin/env python
"""
FunASR 快速测试脚本

快速验证 FunASR 安装和基本功能

Usage:
    python backend/test/quick_funasr_test.py
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 设置 ModelScope 缓存目录（避免下载到 C 盘）
if not os.environ.get('MODELSCOPE_CACHE'):
    # 使用默认路径（quick_funasr_test.py 在 backend/test/ 目录下）
    _backend_dir = Path(__file__).parent.parent  # backend/
    _default_cache_dir = _backend_dir / 'data' / 'asr' / '.cache'
    os.environ['MODELSCOPE_CACHE'] = str(_default_cache_dir.resolve())


def print_header(text):
    """打印标题"""
    print(f"\n{'=' * 60}")
    print(f"{text}")
    print(f"{'=' * 60}\n")


def test_import():
    """测试导入"""
    print_header("1. 测试 funasr 导入")
    
    try:
        import funasr
        from funasr import AutoModel
        print(f"✅ funasr 已安装")
        print(f"   版本: {getattr(funasr, '__version__', 'unknown')}")
        return True
    except ImportError as e:
        print(f"❌ funasr 未安装: {e}")
        print(f"   安装命令: pip install funasr")
        return False


def test_model_loading():
    """测试模型加载"""
    print_header("2. 测试模型加载")
    
    try:
        from funasr import AutoModel
        
        # 检查本地模型（优先使用 backend/data/asr/funasr_nano）
        local_model = Path("backend/data/asr/funasr_nano")
        
        # 检查缓存目录中的模型
        cache_dir = Path(os.environ.get('MODELSCOPE_CACHE', ''))
        cache_model = cache_dir / "models" / "FunAudioLLM" / "Fun-ASR-Nano-2512" if cache_dir else None
        
        # 选择模型
        model_name = None
        
        if local_model.exists():
            print(f"✅ 发现本地模型: {local_model}")
            model_dir = str(local_model.resolve())
            model_name = "local"
        elif cache_model and cache_model.exists():
            print(f"✅ 使用缓存模型: {cache_model}")
            print("⚠️  注意: Fun-ASR-Nano-2512 在 FunASR 1.3.0 中可能有兼容性问题")
            print("建议使用更稳定的 Paraformer 模型")
            model_dir = "iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
            model_name = "paraformer"
        else:
            print(f"⚠️  本地模型不存在，使用经典 Paraformer 模型")
            print(f"📁 缓存目录: {os.environ.get('MODELSCOPE_CACHE', 'default')}")
            model_dir = "iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
            model_name = "paraformer"
        
        print(f"正在加载模型: {model_dir}")
        print("（首次加载可能需要下载，请耐心等待...）")
        
        model = AutoModel(
            model=model_dir,
            device="gpu",
            disable_update=True,  # 禁用自动更新检查
        )
        
        print(f"✅ 模型加载成功")
        print(f"   模型路径: {model.model_path}")
        
        return True, model
        
    except Exception as e:
        print(f"❌ 模型加载失败: {e}")
        return False, None


def test_recognition(model):
    """测试识别功能"""
    print_header("3. 测试语音识别")
    
    try:
        # 检查示例音频
        example_audio = Path(model.model_path) / "example" / "zh.mp3"
        
        if not example_audio.exists():
            print(f"⚠️  示例音频不存在: {example_audio}")
            print(f"   跳过识别测试")
            return True
        
        print(f"使用示例音频: {example_audio}")
        print("正在识别...")
        
        res = model.generate(
            input=[str(example_audio)],
            cache={},
            batch_size=1,
            language="中文",
            itn=True,
        )
        
        text = res[0]["text"]
        print(f"✅ 识别成功")
        print(f"   结果: {text}")
        
        return True
        
    except Exception as e:
        print(f"❌ 识别失败: {e}")
        return False


def main():
    """主流程"""
    print_header("FunASR 快速测试")
    
    # 1. 测试导入
    if not test_import():
        print("\n❌ 请先安装 funasr: pip install funasr")
        return 1
    
    # 2. 测试模型加载
    success, model = test_model_loading()
    if not success:
        print("\n❌ 模型加载失败")
        print("   请检查:")
        print("   1. 网络连接是否正常")
        print("   2. 是否需要配置 HuggingFace 镜像")
        print("   3. 本地模型路径是否正确")
        return 1
    
    # 3. 测试识别
    if not test_recognition(model):
        print("\n❌ 识别测试失败")
        return 1
    
    print_header("测试完成")
    print("✅ 所有测试通过")
    print("\n下一步:")
    print("  1. 在 core_config.json 中配置 ASR")
    print("  2. 运行完整测试: python backend/test/test_funasr_automodel.py")
    print("  3. 启动主服务: python backend/main.py")
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
