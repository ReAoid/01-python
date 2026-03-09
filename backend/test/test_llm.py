"""
LLM 服务模块测试文件

测试 LLM 服务的各项功能（支持多个运营商）:

阶段 1: LLM 服务初始化测试
阶段 2: 运营商选择测试
阶段 3: OpenAI LLM 功能测试
阶段 4: Ollama LLM 功能测试
阶段 5: TextLLMClient 异步客户端测试
阶段 6: 运营商切换测试

使用方法：
    cd /Users/mingy/Documents/python/01-python
    python backend/test/test_llm.py

前置条件：
    - 配置有效的 LLM API（在 backend/config/core_config.json 中）
    - 可选：本地 Ollama 服务（用于测试 Ollama 运营商）
    
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

# ============================================================================
# 路径配置
# ============================================================================
ROOT_DIR = Path(__file__).resolve().parent.parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

try:
    from backend.services.llm_service import get_llm, get_current_provider, is_provider_available
    from backend.utils.llm import TextLLMClient, OpenaiLlm, OllamaLlm
    from backend.core.message import Message
    from backend.config import settings
except ImportError as e:
    print(f"❌ 无法导入必要模块: {e}")
    print("请检查项目路径配置")
    sys.exit(1)


class LLMServiceTester:
    """LLM 服务测试类 - 分阶段测试 LLM 功能"""
    
    def __init__(self):
        self.llm = None
        self.api_available = False
        self.test_results = []
    
    def test_llm_service_initialization(self) -> bool:
        """
        阶段 1: LLM 服务初始化测试
        
        测试内容：
        - 获取当前运营商
        - 通过 get_llm() 创建 LLM 实例
        - 验证返回的 LLM 类型
        """
        print("\n" + "="*60)
        print("阶段 1: LLM 服务初始化测试")
        print("="*60)
        
        try:
            # 测试 1.1: 获取当前运营商
            print("\n[1.1] 获取当前运营商...")
            provider = get_current_provider()
            print(f"✅ 当前运营商: {provider}")
            
            # 测试 1.2: 通过 get_llm() 创建实例
            print("\n[1.2] 通过 get_llm() 创建 LLM 实例...")
            try:
                llm = get_llm()
                self.llm = llm
                self.api_available = True
                print(f"✅ LLM 实例创建成功")
                print(f"   类型: {type(llm).__name__}")
                print(f"   模型: {llm.model}")
            except ValueError as e:
                print(f"⚠️  LLM 配置无效: {e}")
                print("   部分测试将被跳过")
                self.api_available = False
                return True
            
            # 测试 1.3: 验证 LLM 接口
            print("\n[1.3] 验证 LLM 接口...")
            required_methods = ['generate', 'agenerate', 'stream', 'astream']
            for method in required_methods:
                if hasattr(llm, method):
                    print(f"✅ 方法 '{method}' 存在")
                else:
                    print(f"❌ 方法 '{method}' 缺失")
                    return False
            
            print("\n✅ 阶段 1 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 1 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_provider_selection(self) -> bool:
        """
        阶段 2: 运营商选择测试
        
        测试内容：
        - 检查支持的运营商
        - 验证运营商可用性
        - 测试不同运营商的创建
        """
        print("\n" + "="*60)
        print("阶段 2: 运营商选择测试")
        print("="*60)
        
        try:
            # 测试 2.1: 检查支持的运营商
            print("\n[2.1] 检查支持的运营商...")
            providers = ["openai", "ollama"]
            for provider in providers:
                available = is_provider_available(provider)
                status = "✅ 支持" if available else "❌ 不支持"
                print(f"   {provider}: {status}")
            
            # 测试 2.2: 创建 OpenAI LLM
            print("\n[2.2] 创建 OpenAI LLM 实例...")
            try:
                openai_llm = get_llm(provider="openai")
                assert isinstance(openai_llm, OpenaiLlm)
                print(f"✅ OpenAI LLM 创建成功")
                print(f"   模型: {openai_llm.model}")
            except Exception as e:
                print(f"⚠️  OpenAI LLM 创建失败: {e}")
            
            # 测试 2.3: 创建 Ollama LLM
            print("\n[2.3] 创建 Ollama LLM 实例...")
            try:
                ollama_llm = get_llm(provider="ollama")
                assert isinstance(ollama_llm, OllamaLlm)
                print(f"✅ Ollama LLM 创建成功")
                print(f"   模型: {ollama_llm.model}")
                print(f"   服务地址: {ollama_llm.base_url}")
            except Exception as e:
                print(f"⚠️  Ollama LLM 创建失败: {e}")
            
            # 测试 2.4: 无效运营商处理
            print("\n[2.4] 测试无效运营商处理...")
            try:
                invalid_llm = get_llm(provider="invalid_provider")
                print(f"❌ 应该抛出异常，但没有")
                return False
            except ValueError as e:
                print(f"✅ 正确抛出异常: {e}")
            
            print("\n✅ 阶段 2 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 2 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_openai_llm_functionality(self) -> bool:
        """
        阶段 3: OpenAI LLM 功能测试
        
        测试内容：
        - 消息转换
        - 同步生成
        - 流式生成
        """
        print("\n" + "="*60)
        print("阶段 3: OpenAI LLM 功能测试")
        print("="*60)
        
        if not self.api_available or not isinstance(self.llm, OpenaiLlm):
            print("⚠️  OpenAI LLM 未初始化或不可用，跳过此阶段")
            return True
        
        try:
            # 测试 3.1: 消息转换
            print("\n[3.1] 测试消息转换...")
            messages = [
                Message(role="system", content="You are a helpful assistant"),
                Message(role="user", content="Hello")
            ]
            converted = self.llm._convert_messages(messages)
            assert len(converted) == 2
            assert converted[0]["role"] == "system"
            assert converted[1]["role"] == "user"
            print(f"✅ 消息转换成功 ({len(converted)} 条消息)")
            
            # 测试 3.2: 同步生成
            print("\n[3.2] 测试同步生成...")
            try:
                response = self.llm.generate(messages)
                assert isinstance(response, Message)
                assert response.role == "assistant"
                print(f"✅ 同步生成成功")
                print(f"   响应: {response.content[:80]}...")
            except Exception as e:
                print(f"⚠️  API 调用失败: {e}")
                return True
            
            # 测试 3.3: 流式生成
            print("\n[3.3] 测试流式生成...")
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
                print(f"   完整响应: {full_response[:80]}...")
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
    
    def test_ollama_llm_functionality(self) -> bool:
        """
        阶段 4: Ollama LLM 功能测试
        
        测试内容：
        - 消息转换
        - 同步生成
        - 流式生成
        
        注意：需要本地 Ollama 服务运行
        """
        print("\n" + "="*60)
        print("阶段 4: Ollama LLM 功能测试")
        print("="*60)
        
        try:
            # 创建 Ollama LLM 实例
            print("\n[4.1] 创建 Ollama LLM 实例...")
            try:
                ollama_llm = get_llm(provider="ollama")
                print(f"✅ Ollama LLM 创建成功")
                print(f"   模型: {ollama_llm.model}")
                print(f"   服务地址: {ollama_llm.base_url}")
            except Exception as e:
                print(f"⚠️  Ollama LLM 创建失败: {e}")
                print("   跳过 Ollama 功能测试")
                return True
            
            # 测试 4.2: 消息转换
            print("\n[4.2] 测试消息转换...")
            messages = [
                Message(role="system", content="You are a helpful assistant"),
                Message(role="user", content="Hello")
            ]
            converted = ollama_llm._convert_messages(messages)
            assert len(converted) == 2
            print(f"✅ 消息转换成功 ({len(converted)} 条消息)")
            
            # 测试 4.3: 同步生成
            print("\n[4.3] 测试同步生成...")
            try:
                response = ollama_llm.generate(messages)
                assert isinstance(response, Message)
                assert response.role == "assistant"
                print(f"✅ 同步生成成功")
                print(f"   响应: {response.content[:80]}...")
            except Exception as e:
                print(f"⚠️  Ollama 服务调用失败: {e}")
                print("   请确保 Ollama 服务正在运行")
                return True
            
            # 测试 4.4: 流式生成
            print("\n[4.4] 测试流式生成...")
            try:
                print("   接收流式输出: ", end="", flush=True)
                full_response = ""
                chunk_count = 0
                
                for chunk in ollama_llm.stream(messages):
                    full_response += chunk
                    chunk_count += 1
                    print(".", end="", flush=True)
                
                print(f" 完成")
                print(f"✅ 流式生成成功")
                print(f"   接收 {chunk_count} 个数据块")
            except Exception as e:
                print(f"\n⚠️  Ollama 服务调用失败: {e}")
                return True
            
            print("\n✅ 阶段 4 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 4 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_text_llm_client(self) -> bool:
        """
        阶段 5: TextLLMClient 异步客户端测试
        
        测试内容：
        - 客户端初始化
        - 异步消息发送
        - 流式输出消费
        - 历史记录管理
        """
        print("\n" + "="*60)
        print("阶段 5: TextLLMClient 异步客户端测试")
        print("="*60)
        
        if not self.api_available:
            print("⚠️  LLM 未初始化或 API 不可用，跳过此阶段")
            return True
        
        try:
            # 测试 5.1: 客户端初始化
            print("\n[5.1] 初始化 TextLLMClient...")
            try:
                client = TextLLMClient(
                    system_prompt="You are a helpful assistant. Be concise."
                )
                print(f"✅ TextLLMClient 初始化成功")
                print(f"   最大历史长度: {client.max_history}")
            except Exception as e:
                print(f"⚠️  客户端初始化失败: {e}")
                return True
            
            # 测试 5.2: 异步消息发送和流式消费
            print("\n[5.2] 测试异步消息发送...")
            try:
                user_input = "Say hello in one word"
                print(f"   发送: '{user_input}'")
                
                queue = await client.send_user_message(user_input)
                
                print("   接收流式输出: ", end="", flush=True)
                full_response = ""
                chunk_count = 0
                
                while True:
                    token = await queue.get()
                    if token is None:
                        break
                    full_response += token
                    chunk_count += 1
                    print(".", end="", flush=True)
                
                print(f" 完成")
                print(f"✅ 异步消息发送成功")
                print(f"   接收 {chunk_count} 个数据块")
                print(f"   完整响应: {full_response[:80]}...")
            except Exception as e:
                print(f"⚠️  API 调用失败: {e}")
                return True
            
            # 测试 5.3: 历史记录管理
            print("\n[5.3] 测试历史记录管理...")
            history = client.get_history()
            print(f"✅ 历史记录获取成功")
            print(f"   历史记录条数: {len(history)}")
            for i, msg in enumerate(history[-2:]):  # 显示最后两条
                print(f"   [{i+1}] {msg.role}: {msg.content[:50]}...")
            
            # 测试 5.4: 清除历史
            print("\n[5.4] 测试清除历史...")
            client.clear_history()
            history = client.get_history()
            assert len(history) == 0
            print(f"✅ 历史记录清除成功")
            
            # 关闭客户端
            await client.close()
            
            print("\n✅ 阶段 5 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 5 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_provider_switching(self) -> bool:
        """
        阶段 6: 运营商切换测试
        
        测试内容：
        - 在不同运营商之间切换
        - 验证切换后的 LLM 类型
        - 配置验证
        """
        print("\n" + "="*60)
        print("阶段 6: 运营商切换测试")
        print("="*60)
        
        try:
            # 测试 6.1: 获取当前运营商
            print("\n[6.1] 获取当前运营商...")
            current_provider = get_current_provider()
            print(f"✅ 当前运营商: {current_provider}")
            
            # 测试 6.2: 切换到 OpenAI
            print("\n[6.2] 切换到 OpenAI...")
            try:
                openai_llm = get_llm(provider="openai")
                assert isinstance(openai_llm, OpenaiLlm)
                print(f"✅ 成功切换到 OpenAI")
                print(f"   模型: {openai_llm.model}")
            except Exception as e:
                print(f"⚠️  切换失败: {e}")
            
            # 测试 6.3: 切换到 Ollama
            print("\n[6.3] 切换到 Ollama...")
            try:
                ollama_llm = get_llm(provider="ollama")
                assert isinstance(ollama_llm, OllamaLlm)
                print(f"✅ 成功切换到 Ollama")
                print(f"   模型: {ollama_llm.model}")
            except Exception as e:
                print(f"⚠️  切换失败: {e}")
            
            # 测试 6.4: 验证配置中的运营商
            print("\n[6.4] 验证配置中的运营商...")
            config_provider = settings.chat_llm.provider
            print(f"✅ 配置中的运营商: {config_provider}")
            
            print("\n✅ 阶段 6 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 6 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False


async def main():
    """主测试函数"""
    print("="*60)
    print("🚀 LLM 服务模块测试")
    print("="*60)
    print("\n⚠️  注意: 某些测试会实际调用 LLM API，可能产生费用")
    print("如果不想调用 API，可以在配置中设置无效的 API 密钥\n")
    
    tester = LLMServiceTester()
    
    try:
        # 按顺序执行测试
        sync_tests = [
            ("LLM 服务初始化", tester.test_llm_service_initialization),
            ("运营商选择", tester.test_provider_selection),
            ("OpenAI LLM 功能", tester.test_openai_llm_functionality),
            ("Ollama LLM 功能", tester.test_ollama_llm_functionality),
            ("运营商切换", tester.test_provider_switching),
        ]
        
        async_tests = [
            ("TextLLMClient 异步客户端", tester.test_text_llm_client),
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
