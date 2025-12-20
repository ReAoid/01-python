import asyncio
import sys
import json
import wave
from pathlib import Path
from typing import Optional, Tuple

# -----------------------------------------------------------------------------
# 路径配置
# -----------------------------------------------------------------------------
# 1. 确定项目根目录 (01-python)
# 当前文件: backend/test/test_genie_startup.py
# parent -> backend/test
# parent.parent -> backend
# parent.parent.parent -> 01-python (项目根目录)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# 2. 确保 backend 模块可以被导入
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

try:
    from backend.utils.genie_client import GenieTTS
except ImportError:
    print("❌ 无法导入 backend.utils.genie_client，请检查路径设置")
    sys.exit(1)


class GenieTester:
    def __init__(self):
        self.client: Optional[GenieTTS] = None
        self.model_dir: Optional[Path] = None
        self.ref_audio_path: Optional[Path] = None
        self.ref_text: str = ""
        self.output_wav = "test_output.wav"

    async def check_paths(self) -> bool:
        """步骤 1: 检查模型和配置文件路径"""
        print("\n[1/5] 检查模型路径配置...")
        
        # 修正后的模型路径
        base_model_path = PROJECT_ROOT / "backend/config/tts/GenieData/CharacterModels/v2ProPlus/feibi"
        print(f"    - 目标模型路径: {base_model_path}")

        if not base_model_path.exists():
            print(f"❌ 错误: 未找到模型目录: {base_model_path}")
            print(f"    - 当前工作目录: {Path.cwd()}")
            print(f"    - PROJECT_ROOT: {PROJECT_ROOT}")
            return False

        self.model_dir = base_model_path / "tts_models"
        config_path = base_model_path / "prompt_wav.json"

        if not self.model_dir.exists():
            print(f"❌ 错误: tts_models 子目录不存在: {self.model_dir}")
            return False
        
        if not config_path.exists():
            print(f"❌ 错误: 配置文件不存在: {config_path}")
            return False

        # 读取参考音频配置
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                ref_wav_name = config["Normal"]["wav"]
                self.ref_text = config["Normal"]["text"]
            
            self.ref_audio_path = base_model_path / "prompt_wav" / ref_wav_name
            
            if not self.ref_audio_path.exists():
                print(f"❌ 错误: 参考音频文件不存在: {self.ref_audio_path}")
                return False
                
        except Exception as e:
            print(f"❌ 读取模型配置失败: {e}")
            return False

        print("✅ 路径检查通过")
        return True

    async def connect_service(self) -> bool:
        """步骤 2: 连接 TTS 服务"""
        print("\n[2/5] 连接服务器 (127.0.0.1:8001)...")
        self.client = GenieTTS()
        if not await self.client.connect():
            print("❌ 连接失败！请确保 Genie TTS 服务已在 8001 端口启动。")
            return False
        print("✅ 服务器连接成功")
        return True

    async def load_character(self) -> bool:
        """步骤 3: 加载角色模型"""
        print("\n[3/5] 加载角色模型...")
        if not self.client or not self.model_dir:
            print("❌ 前置条件未满足 (Client 或 Model Dir 为空)")
            return False

        # character_name 只是标识符，关键是 onnx_model_dir
        if not await self.client.load_character("feibi_test", str(self.model_dir)):
            print("❌ 加载角色失败")
            return False
        print("✅ 角色加载成功")
        return True

    async def set_reference(self) -> bool:
        """步骤 4: 设置参考音频"""
        print("\n[4/5] 设置参考音频...")
        if not self.client or not self.ref_audio_path:
            print("❌ 前置条件未满足 (Client 或 Reference Audio Path 为空)")
            return False

        if not await self.client.set_reference_audio(str(self.ref_audio_path), self.ref_text, "zh"):
            print("❌ 设置参考音频失败")
            return False
        print("✅ 参考音频设置成功")
        return True

    async def synthesize_test(self) -> bool:
        """步骤 5: 合成测试与保存"""
        text = "你好，这是一个测试音频，用于验证服务是否正常运行。"
        print(f"\n[5/5] 正在合成: '{text}'")
        
        if not self.client:
            return False

        try:
            all_audio_data = bytearray()
            chunk_count = 0
            
            print("    - 接收数据流: ", end="")
            async for chunk in self.client.synthesize_stream(text):
                chunk_count += 1
                all_audio_data.extend(chunk)
                print(".", end="", flush=True)
            print(" 完成")

            if chunk_count == 0:
                print("\n❌ 未接收到任何音频数据")
                return False

            print(f"    - 接收 {chunk_count} 个音频块，共 {len(all_audio_data)} 字节")
            
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
        if self.client:
            await self.client.close()

async def main():
    tester = GenieTester()
    
    try:
        # 按顺序执行测试步骤
        if not await tester.check_paths():
            return
            
        if not await tester.connect_service():
            return
            
        if not await tester.load_character():
            return
            
        if not await tester.set_reference():
            return
            
        if not await tester.synthesize_test():
            return
            
        print("\n✨ 所有测试步骤完成! ✨")
        
    finally:
        await tester.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n测试已取消")
