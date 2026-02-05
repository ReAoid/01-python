"""
Config 配置模块测试文件

测试 Config 模块的各项功能（清晰分阶段测试）:

阶段 1: Settings 配置加载测试
阶段 2: 配置模型验证测试
阶段 3: 配置修改和保存测试
阶段 4: 路径配置测试

使用方法：
    cd /Users/mingy/Documents/python/01-python
    python backend/test/test_config.py
"""

import sys
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# 路径配置
# -----------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent.parent

# 确保 backend 模块可以被导入
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

try:
    from backend.config import settings, paths
    from backend.config.settings import (
        ChatLLMConfig,
        EmbeddingLLMConfig,
        TTSConfig,
        ASRConfig,
        MemoryConfig
    )
except ImportError as e:
    print(f"❌ 无法导入必要模块: {e}")
    print("请检查项目路径配置")
    sys.exit(1)


class ConfigTester:
    """Config 模块测试类 - 分阶段测试配置功能"""
    
    def __init__(self):
        self.test_results = []
    
    def test_settings_loading(self) -> bool:
        """
        阶段 1: Settings 配置加载测试
        
        测试内容：
        - 加载全局配置
        - 验证配置结构
        - 检查默认值
        """
        print("\n" + "="*60)
        print("阶段 1: Settings 配置加载测试")
        print("="*60)
        
        try:
            # 测试 1.1: 加载全局配置
            print("\n[1.1] 加载全局配置...")
            assert settings is not None
            print("✅ 全局配置加载成功")
            
            # 测试 1.2: 聊天LLM配置
            print("\n[1.2] 检查聊天LLM配置...")
            assert hasattr(settings, 'chat_llm')
            assert isinstance(settings.chat_llm, ChatLLMConfig)
            print(f"✅ 聊天LLM配置:")
            print(f"   模型: {settings.chat_llm.model}")
            print(f"   提供商: {settings.chat_llm.provider}")
            print(f"   温度: {settings.chat_llm.temperature}")
            
            # 测试 1.3: 嵌入LLM配置
            print("\n[1.3] 检查嵌入LLM配置...")
            assert hasattr(settings, 'embedding_llm')
            assert isinstance(settings.embedding_llm, EmbeddingLLMConfig)
            print(f"✅ 嵌入LLM配置:")
            print(f"   模型: {settings.embedding_llm.model}")
            
            # 测试 1.4: 记忆配置
            print("\n[1.4] 检查记忆配置...")
            assert hasattr(settings, 'memory')
            assert isinstance(settings.memory, MemoryConfig)
            print(f"✅ 记忆配置:")
            print(f"   最大历史长度: {settings.memory.max_history_length}")
            print(f"   检索top_k: {settings.memory.retrieval_top_k}")
            
            # 测试 1.5: TTS配置
            print("\n[1.5] 检查TTS配置...")
            assert hasattr(settings, 'tts')
            assert isinstance(settings.tts, TTSConfig)
            print(f"✅ TTS配置:")
            print(f"   启用: {settings.tts.enabled}")
            print(f"   引擎: {settings.tts.engine}")
            print(f"   语言: {settings.tts.language}")
            
            # 测试 1.6: ASR配置
            print("\n[1.6] 检查ASR配置...")
            assert hasattr(settings, 'asr')
            assert isinstance(settings.asr, ASRConfig)
            print(f"✅ ASR配置:")
            print(f"   启用: {settings.asr.enabled}")
            print(f"   引擎: {settings.asr.engine}")
            print(f"   语言: {settings.asr.language}")
            
            print("\n✅ 阶段 1 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 1 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_config_validation(self) -> bool:
        """
        阶段 2: 配置模型验证测试
        
        测试内容：
        - 创建配置对象
        - 验证字段约束
        - 测试默认值
        """
        print("\n" + "="*60)
        print("阶段 2: 配置模型验证测试")
        print("="*60)
        
        try:
            # 测试 2.1: 创建聊天LLM配置
            print("\n[2.1] 创建聊天LLM配置...")
            chat_config = ChatLLMConfig(
                model="gpt-4",
                provider="openai",
                temperature=0.8
            )
            assert chat_config.model == "gpt-4"
            assert chat_config.temperature == 0.8
            print("✅ 聊天LLM配置创建成功")
            
            # 测试 2.2: 测试默认值
            print("\n[2.2] 测试配置默认值...")
            default_memory = MemoryConfig()
            assert default_memory.max_history_length == 10
            assert default_memory.retrieval_top_k == 5
            print("✅ 默认值正确")
            print(f"   最大历史长度: {default_memory.max_history_length}")
            print(f"   检索top_k: {default_memory.retrieval_top_k}")
            
            # 测试 2.3: 修改配置值
            print("\n[2.3] 修改配置值...")
            memory_config = MemoryConfig(
                max_history_length=20,
                retrieval_top_k=10
            )
            assert memory_config.max_history_length == 20
            assert memory_config.retrieval_top_k == 10
            print("✅ 配置值修改成功")
            
            print("\n✅ 阶段 2 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 2 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_config_persistence(self) -> bool:
        """
        阶段 3: 配置修改和保存测试
        
        测试内容：
        - 配置文件路径
        - 配置序列化
        """
        print("\n" + "="*60)
        print("阶段 3: 配置修改和保存测试")
        print("="*60)
        
        try:
            # 测试 3.1: 配置对象转字典
            print("\n[3.1] 配置对象转字典...")
            config_dict = settings.model_dump()
            assert isinstance(config_dict, dict)
            assert 'chat_llm' in config_dict
            assert 'memory' in config_dict
            print(f"✅ 配置转字典成功 ({len(config_dict)} 个配置项)")
            
            # 测试 3.2: 配置 JSON 序列化
            print("\n[3.2] 配置 JSON 序列化...")
            import json
            config_json = json.dumps(config_dict, indent=2, ensure_ascii=False)
            assert len(config_json) > 0
            print(f"✅ JSON 序列化成功 ({len(config_json)} 字节)")
            
            print("\n✅ 阶段 3 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 3 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_path_configuration(self) -> bool:
        """
        阶段 4: 路径配置测试
        
        测试内容：
        - 项目路径
        - 数据目录路径
        - 日志路径
        """
        print("\n" + "="*60)
        print("阶段 4: 路径配置测试")
        print("="*60)
        
        try:
            # 测试 4.1: 项目根路径
            print("\n[4.1] 检查项目根路径...")
            assert hasattr(paths, 'ROOT_DIR')
            assert Path(paths.ROOT_DIR).exists()
            print(f"✅ 项目根路径: {paths.ROOT_DIR}")
            
            # 测试 4.2: 数据目录路径
            print("\n[4.2] 检查数据目录路径...")
            if hasattr(paths, 'DATA_DIR'):
                print(f"✅ 数据目录: {paths.DATA_DIR}")
            else:
                print("⚠️  数据目录路径未配置")
            
            # 测试 4.3: 日志路径
            print("\n[4.3] 检查日志路径...")
            if hasattr(paths, 'LOG_DIR'):
                print(f"✅ 日志目录: {paths.LOG_DIR}")
            else:
                print("⚠️  日志目录路径未配置")
            
            # 测试 4.4: 记忆目录路径
            print("\n[4.4] 检查记忆目录路径...")
            if hasattr(paths, 'MEMORY_DIR'):
                print(f"✅ 记忆目录: {paths.MEMORY_DIR}")
            else:
                print("⚠️  记忆目录路径未配置")
            
            print("\n✅ 阶段 4 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 4 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """主测试函数"""
    print("="*60)
    print("🚀 Config 配置模块测试")
    print("="*60)
    
    tester = ConfigTester()
    
    try:
        # 按顺序执行测试
        tests = [
            ("Settings 配置加载", tester.test_settings_loading),
            ("配置模型验证", tester.test_config_validation),
            ("配置持久化", tester.test_config_persistence),
            ("路径配置", tester.test_path_configuration),
        ]
        
        results = []
        for test_name, test_func in tests:
            result = test_func()
            results.append((test_name, result))
        
        # 打印测试总结
        print("\n" + "="*60)
        print("测试总结")
        print("="*60)
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = "✅ 通过" if result else "❌ 失败"
            print(f"{test_name}: {status}")
        
        print("="*60)
        print(f"总计: {passed}/{total} 通过")
        
        if passed == total:
            print("✨ 所有测试通过！")
            return True
        else:
            print(f"⚠️  {total - passed} 个测试失败")
            return False
        
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(1)
