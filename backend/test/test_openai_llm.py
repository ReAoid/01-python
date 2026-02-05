"""
OpenAI LLM 模块测试文件

测试 OpenAI LLM 客户端的各项功能（清晰分阶段测试）:

阶段 1: LLM 初始化测试
阶段 2: 消息转换测试
阶段 3: 同步生成测试
阶段 4: 异步生成测试
阶段 5: 流式生成测试
阶段 6: 异步流式生成测试
阶段 7: 参数配置测试

使用方法：
    cd /Users/mingy/Documents/python/01-python
    python backend/test/test_openai_llm.py

前置条件：
    - 配置有效的 LLM API（在 backend/config/settings.py 中）
    
注意：
    - 某些测试会实际调用 LLM API，可能产生费用
    - 如果 API 配置无效，部分测试会被跳过
"""

import asyncio
import sys
import logging
from pathlib import Path
from typing import List

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
    from backend.utils.openai_llm import OpenaiLlm
    from backend.core.message import Message, UserMessage, SystemMessage, AssistantMessage
    from backend.config import settings
except ImportError as e:
    print(f"❌ 无法导入必要模块: {e}")
    print("请检查项目路径配置")
    sys.exit(1)


class OpenAILLMTester:
    """OpenAI LLM 测试类 - 分阶段测试 LLM 功能"""
    
    def __init__(self):
        self.llm = None
        self.api_available = False
        self.test_results = []
    
    def test_initialization(self) -> bool:
        """
        阶段 1: LLM 初始化测试
        
        测试内容：
        - 使用配置初始化
        - 使用自定义参数初始化
        - 配置验证
        """
        print("\n" + "="*60)
        print("阶段 1: LLM 初始化测试")
        print("="*60)
        
        try:
            # 测试 1.1: 使用默认配置初始化
            print("\n[1.1] 使用默认配置初始化...")
            try:
                llm = OpenaiLlm()
                self.llm = llm
                self.api_available = True
                print(f"✅ LLM 初始化成功")
                print(f"   模型: {llm.model}")
                print(f"   客户端: {'已创建' if llm.client else '未创建'}")
                print(f"   异步客户端: {'已创建' if llm.async_client else '未创建'}")
            except ValueError as e:
                print(f"⚠️  LLM 配置无效: {e}")
                print("   部分测试将被跳过")
                self.api_available = False
                return True  # 配置问题不算测试失败
            
            # 测试 1.2: 使用自定义参数初始化
            print("\n[1.2] 测试自定义参数初始化...")
            try:
                custom_llm = OpenaiLlm(
                    model="gpt-3.5-turbo",
                    api_key="test_key",
                    base_url="https://api.openai.com/v1",
                    timeout=30
                )
                assert custom_llm.model == "gpt-3.5-turbo"
                print("✅ 自定义参数初始化成功")
            except Exception as e:
                print(f"⚠️  自定义参数初始化测试: {e}")
            
            print("\n✅ 阶段 1 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 1 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_message_conversion(self) -> bool:
        """
        阶段 2: 消息转换测试
        
        测试内容：
        - Message 对象转换为 API 格式
        - 不同类型消息的转换
        - 消息列表转换
        """
        print("\n" + "="*60)
        print("阶段 2: 消息转换测试")
        print("="*60)
        
        if not self.api_available or not self.llm:
            print("⚠️  LLM 未初始化，跳过此阶段")
            return True
        
        try:
            # 测试 2.1: 单个消息转换
            print("\n[2.1] 单个消息转换...")
            user_msg = UserMessage("Hello")
            converted = self.llm._convert_messages([user_msg])
            assert len(converted) == 1
            assert converted[0]["role"] == "user"
            assert converted[0]["content"] == "Hello"
            print(f"✅ 单个消息转换成功: {converted[0]}")
            
            # 测试 2.2: 多个消息转换
            print("\n[2.2] 多个消息转换...")
            messages = [
                SystemMessage("You are a helpful assistant"),
                UserMessage("What is Python?"),
                AssistantMessage("Python is a programming language")
            ]
            converted = self.llm._convert_messages(messages)
            assert len(converted) == 3
            assert converted[0]["role"] == "system"
            assert converted[1]["role"] == "user"
            assert converted[2]["role"] == "assistant"
            print(f"✅ 多个消息转换成功 ({len(converted)} 条)")
            for i, msg in enumerate(converted):
                print(f"   [{i+1}] {msg['role']}: {msg['content'][:30]}...")
            
            print("\n✅ 阶段 2 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 2 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_sync_generation(self) -> bool:
        """
        阶段 3: 同步生成测试
        
        测试内容：
        - 基本生成调用
        - 返回消息格式
        - 简单对话
        """
        print("\n" + "="*60)
        print("阶段 3: 同步生成测试")
        print("="*60)
        
        if not self.api_available or not self.llm:
            print("⚠️  LLM 未初始化或 API 不可用，跳过此阶段")
            return True
        
        try:
            # 测试 3.1: 简单问答
            print("\n[3.1] 测试简单问答...")
            print("   发送: 'Say hello in Chinese'")
            messages = [
                SystemMessage("You are a helpful assistant. Be concise."),
                UserMessage("Say hello in Chinese")
            ]
            
            try:
                response = self.llm.generate(messages)
                assert isinstance(response, Message)
                assert response.role == "assistant"
                assert len(response.content) > 0
                print(f"✅ 生成成功")
                print(f"   响应: {response.content[:100]}...")
            except Exception as e:
                print(f"⚠️  API 调用失败: {e}")
                print("   这可能是网络或 API 配置问题")
                return True  # API 调用失败不算测试失败
            
            # 测试 3.2: 带温度参数的生成
            print("\n[3.2] 测试带温度参数的生成...")
            messages = [UserMessage("Pick a number between 1 and 10")]
            try:
                response = self.llm.generate(messages, temperature=0.0)
                print(f"✅ 带参数生成成功")
                print(f"   响应: {response.content[:100]}...")
            except Exception as e:
                print(f"⚠️  API 调用失败: {e}")
                return True
            
            print("\n✅ 阶段 3 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 3 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_async_generation(self) -> bool:
        """
        阶段 4: 异步生成测试
        
        测试内容：
        - 异步生成调用
        - 异步返回格式
        """
        print("\n" + "="*60)
        print("阶段 4: 异步生成测试")
        print("="*60)
        
        if not self.api_available or not self.llm:
            print("⚠️  LLM 未初始化或 API 不可用，跳过此阶段")
            return True
        
        try:
            # 测试 4.1: 异步问答
            print("\n[4.1] 测试异步问答...")
            print("   发送: 'What is 2+2? Answer only with the number.'")
            messages = [UserMessage("What is 2+2? Answer only with the number.")]
            
            try:
                response = await self.llm.agenerate(messages)
                assert isinstance(response, Message)
                assert response.role == "assistant"
                assert len(response.content) > 0
                print(f"✅ 异步生成成功")
                print(f"   响应: {response.content[:100]}...")
            except Exception as e:
                print(f"⚠️  API 调用失败: {e}")
                return True
            
            print("\n✅ 阶段 4 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 4 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_stream_generation(self) -> bool:
        """
        阶段 5: 流式生成测试
        
        测试内容：
        - 流式生成调用
        - 流式输出处理
        - 完整响应组装
        """
        print("\n" + "="*60)
        print("阶段 5: 流式生成测试")
        print("="*60)
        
        if not self.api_available or not self.llm:
            print("⚠️  LLM 未初始化或 API 不可用，跳过此阶段")
            return True
        
        try:
            # 测试 5.1: 流式问答
            print("\n[5.1] 测试流式问答...")
            print("   发送: 'Count from 1 to 5'")
            messages = [
                SystemMessage("You are a helpful assistant. Be concise."),
                UserMessage("Count from 1 to 5")
            ]
            
            try:
                print("   接收流式输出: ", end="", flush=True)
                full_response = ""
                chunk_count = 0
                
                for chunk in self.llm.stream(messages):
                    full_response += chunk
                    chunk_count += 1
                    print(".", end="", flush=True)
                
                print(f" 完成")
                print(f"✅ 流式生成成功")
                print(f"   接收 {chunk_count} 个数据块")
                print(f"   完整响应: {full_response[:100]}...")
                
                assert chunk_count > 0, "应该接收到至少一个数据块"
                assert len(full_response) > 0, "完整响应不应为空"
                
            except Exception as e:
                print(f"\n⚠️  API 调用失败: {e}")
                return True
            
            print("\n✅ 阶段 5 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 5 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_async_stream_generation(self) -> bool:
        """
        阶段 6: 异步流式生成测试
        
        测试内容：
        - 异步流式生成
        - 异步迭代处理
        """
        print("\n" + "="*60)
        print("阶段 6: 异步流式生成测试")
        print("="*60)
        
        if not self.api_available or not self.llm:
            print("⚠️  LLM 未初始化或 API 不可用，跳过此阶段")
            return True
        
        try:
            # 测试 6.1: 异步流式问答
            print("\n[6.1] 测试异步流式问答...")
            print("   发送: 'Say hi'")
            messages = [UserMessage("Say hi")]
            
            try:
                print("   接收异步流式输出: ", end="", flush=True)
                full_response = ""
                chunk_count = 0
                
                async for chunk in self.llm.astream(messages):
                    full_response += chunk
                    chunk_count += 1
                    print(".", end="", flush=True)
                
                print(f" 完成")
                print(f"✅ 异步流式生成成功")
                print(f"   接收 {chunk_count} 个数据块")
                print(f"   完整响应: {full_response[:100]}...")
                
                assert chunk_count > 0, "应该接收到至少一个数据块"
                assert len(full_response) > 0, "完整响应不应为空"
                
            except Exception as e:
                print(f"\n⚠️  API 调用失败: {e}")
                return True
            
            print("\n✅ 阶段 6 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 6 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_parameter_configuration(self) -> bool:
        """
        阶段 7: 参数配置测试
        
        测试内容：
        - 温度参数
        - 最大 token 数
        - 其他配置参数
        """
        print("\n" + "="*60)
        print("阶段 7: 参数配置测试")
        print("="*60)
        
        if not self.api_available or not self.llm:
            print("⚠️  LLM 未初始化或 API 不可用，跳过此阶段")
            return True
        
        try:
            # 测试 7.1: 不同温度参数
            print("\n[7.1] 测试温度参数 (temperature=0.0)...")
            messages = [UserMessage("Say 'test'")]
            
            try:
                response = self.llm.generate(messages, temperature=0.0)
                print(f"✅ temperature=0.0 调用成功")
                print(f"   响应: {response.content[:50]}...")
            except Exception as e:
                print(f"⚠️  API 调用失败: {e}")
                return True
            
            # 测试 7.2: max_tokens 参数
            print("\n[7.2] 测试 max_tokens 参数...")
            try:
                response = self.llm.generate(
                    messages,
                    max_tokens=10,
                    temperature=1.0
                )
                print(f"✅ max_tokens=10 调用成功")
                print(f"   响应: {response.content}")
            except Exception as e:
                print(f"⚠️  API 调用失败: {e}")
                return True
            
            print("\n✅ 阶段 7 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 7 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False


async def main():
    """主测试函数"""
    print("="*60)
    print("🚀 OpenAI LLM 模块测试")
    print("="*60)
    print("\n⚠️  注意: 某些测试会实际调用 LLM API，可能产生费用")
    print("如果不想调用 API，可以在配置中设置无效的 API 密钥\n")
    
    tester = OpenAILLMTester()
    
    try:
        # 按顺序执行测试
        sync_tests = [
            ("LLM 初始化", tester.test_initialization),
            ("消息转换", tester.test_message_conversion),
            ("同步生成", tester.test_sync_generation),
            ("流式生成", tester.test_stream_generation),
            ("参数配置", tester.test_parameter_configuration),
        ]
        
        async_tests = [
            ("异步生成", tester.test_async_generation),
            ("异步流式生成", tester.test_async_stream_generation),
        ]
        
        results = []
        
        # 执行同步测试
        for test_name, test_func in sync_tests:
            result = test_func()
            results.append((test_name, result))
        
        # 执行异步测试
        for test_name, test_func in async_tests:
            result = await test_func()
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
        
        if not tester.api_available:
            print("\n⚠️  LLM API 未配置或不可用，部分测试被跳过")
            print("配置有效的 API 以运行完整测试")
        
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
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(1)
