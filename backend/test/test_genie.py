"""
Genie TTS 引擎测试文件

测试 Genie TTS 引擎的各项功能（清晰分阶段测试）：

阶段 1: 检查模型路径配置
阶段 2: 连接 TTS 服务
阶段 3: 加载角色模型
阶段 4: 设置参考音频
阶段 5: 合成测试与保存

使用方法：
    cd /Users/mingy/Documents/python/01-python
    python backend/test/test_genie.py

前置条件：
    - Genie TTS 服务已在 8001 端口启动
    - 角色模型已下载到 backend/data/tts/GenieData/CharacterModels/
"""

import asyncio
import sys
import logging
import json
import wave
from pathlib import Path
from typing import Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# 路径配置
# -----------------------------------------------------------------------------
# 确定根目录 (01-python)
ROOT_DIR = Path(__file__).resolve().parent.parent.parent

# 确保 backend 模块可以被导入
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

try:
    from backend.utils.tts.genie_engine import _GenieTTSClient as GenieTTS
except ImportError:
    print("❌ 无法导入 backend.utils.tts.genie_engine，请检查路径设置")
    sys.exit(1)


class GenieTester:
    """Genie TTS 测试类 - 分阶段测试 TTS 功能"""
    
    def __init__(self):
        self.client: Optional[GenieTTS] = None
        self.model_dir: Optional[Path] = None
        self.ref_audio_path: Optional[Path] = None
        self.ref_text: str = ""
        self.output_wav = "test_output.wav"

    async def check_paths(self) -> bool:
        """
        阶段 1: 检查模型路径配置
        
        检查内容：
        - 模型目录是否存在
        - 配置文件是否存在
        - 参考音频文件是否存在
        """
        print("\n" + "="*60)
        print("阶段 1: 检查模型路径配置")
        print("="*60)
        
        # 修正后的模型路径
        base_model_path = ROOT_DIR / "backend" / "data" / "tts" / "GenieData" / "CharacterModels" / "v2ProPlus" / "feibi"
        print(f"检查模型路径: {base_model_path}")

        if not base_model_path.exists():
            print(f"❌ 错误: 未找到模型目录")
            print(f"   期望路径: {base_model_path}")
            print(f"   根目录: {ROOT_DIR}")
            return False

        self.model_dir = base_model_path / "tts_models"
        config_path = base_model_path / "prompt_wav.json"

        if not self.model_dir.exists():
            print(f"❌ 错误: tts_models 子目录不存在")
            print(f"   期望路径: {self.model_dir}")
            return False
        
        if not config_path.exists():
            print(f"❌ 错误: 配置文件不存在")
            print(f"   期望路径: {config_path}")
            return False

        # 读取参考音频配置
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                ref_wav_name = config["Normal"]["wav"]
                self.ref_text = config["Normal"]["text"]
            
            self.ref_audio_path = base_model_path / "prompt_wav" / ref_wav_name
            
            if not self.ref_audio_path.exists():
                print(f"❌ 错误: 参考音频文件不存在")
                print(f"   期望路径: {self.ref_audio_path}")
                return False
                
        except Exception as e:
            print(f"❌ 读取模型配置失败: {e}")
            return False

        print("✅ 路径检查通过")
        print(f"   模型目录: {self.model_dir}")
        print(f"   参考音频: {self.ref_audio_path}")
        print(f"   参考文本: {self.ref_text}")
        return True

    async def connect_service(self) -> bool:
        """
        阶段 2: 连接 TTS 服务
        
        检查内容：
        - 服务是否在 8001 端口运行
        - 网络连接是否正常
        """
        print("\n" + "="*60)
        print("阶段 2: 连接 TTS 服务")
        print("="*60)
        print("尝试连接到 127.0.0.1:8001...")
        
        self.client = GenieTTS()
        if not await self.client.connect():
            print("❌ 连接失败！")
            print("   请确保 Genie TTS 服务已在 8001 端口启动")
            return False
        print("✅ 服务器连接成功")
        return True

    async def load_character(self) -> bool:
        """
        阶段 3: 加载角色模型
        
        检查内容：
        - 模型文件是否完整
        - 模型加载是否成功
        """
        print("\n" + "="*60)
        print("阶段 3: 加载角色模型")
        print("="*60)
        
        if not self.client or not self.model_dir:
            print("❌ 前置条件未满足 (Client 或 Model Dir 为空)")
            return False

        print(f"加载模型: {self.model_dir}")
        # character_name 只是标识符，关键是 onnx_model_dir
        if not await self.client.load_character("feibi_test", str(self.model_dir)):
            print("❌ 加载角色失败")
            return False
        print("✅ 角色加载成功")
        return True

    async def set_reference(self) -> bool:
        """
        阶段 4: 设置参考音频
        
        检查内容：
        - 参考音频格式是否正确
        - 参考文本是否有效
        """
        print("\n" + "="*60)
        print("阶段 4: 设置参考音频")
        print("="*60)
        
        if not self.client or not self.ref_audio_path:
            print("❌ 前置条件未满足 (Client 或 Reference Audio Path 为空)")
            return False

        print(f"参考音频: {self.ref_audio_path}")
        print(f"参考文本: {self.ref_text}")
        
        if not await self.client.set_reference_audio(str(self.ref_audio_path), self.ref_text, "zh"):
            print("❌ 设置参考音频失败")
            return False
        print("✅ 参考音频设置成功")
        return True

    async def synthesize_test(self) -> bool:
        """
        阶段 5: 合成测试与保存
        
        测试内容：
        - 文本转语音合成
        - 音频流接收
        - WAV 文件保存
        """
        print("\n" + "="*60)
        print("阶段 5: 合成测试与保存")
        print("="*60)
        
        text = "你好，这是一个测试音频，用于验证 Genie TTS 服务是否正常运行。"
        print(f"测试文本: {text}")
        
        
        if not self.client:
            return False

        try:
            all_audio_data = bytearray()
            chunk_count = 0
            
            print("接收音频流: ", end="")
            async for chunk in self.client.synthesize_stream(text):
                chunk_count += 1
                all_audio_data.extend(chunk)
                print(".", end="", flush=True)
            print(" 完成")

            if chunk_count == 0:
                print("\n❌ 未接收到任何音频数据")
                return False

            print(f"接收到 {chunk_count} 个音频块，总计 {len(all_audio_data)} 字节")
            
            # 保存 WAV
            with wave.open(self.output_wav, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(32000)
                wav_file.writeframes(all_audio_data)
            
            print(f"✅ 音频已保存至: {Path(self.output_wav).resolve()}")
            return True

        except Exception as e:
            print(f"\n❌ 合成过程出错: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def cleanup(self):
        """清理资源"""
        if self.client:
            await self.client.close()
            print("\n🔌 已断开服务器连接")


async def main():
    """主测试函数"""
    print("="*60)
    print("🚀 Genie TTS 引擎测试")
    print("="*60)
    
    tester = GenieTester()
    all_passed = True
    
    try:
        # 按顺序执行测试步骤
        tests = [
            ("检查模型路径", tester.check_paths),
            ("连接服务", tester.connect_service),
            ("加载角色模型", tester.load_character),
            ("设置参考音频", tester.set_reference),
            ("合成测试", tester.synthesize_test),
        ]
        
        for test_name, test_func in tests:
            if not await test_func():
                print(f"\n❌ 测试失败: {test_name}")
                all_passed = False
                break
        
        if all_passed:
            print("\n" + "="*60)
            print("✨ 所有测试阶段完成！")
            print("="*60)
        
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    finally:
        await tester.cleanup()
    
    return all_passed


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(1)

