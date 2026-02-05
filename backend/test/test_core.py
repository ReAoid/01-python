"""
Core 核心模块测试文件

测试 Core 模块的各项功能（清晰分阶段测试）:

阶段 1: Message 消息系统测试
阶段 2: Tool 工具基类测试
阶段 3: EventBus 事件总线测试
阶段 4: Logger 日志系统测试

使用方法：
    cd /Users/mingy/Documents/python/01-python
    python backend/test/test_core.py
"""

import asyncio
import sys
import logging
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

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
    from backend.core.message import (
        Message,
        MessageRole,
        SystemMessage,
        UserMessage,
        AssistantMessage
    )
    from backend.core.tool import Tool, ToolParameter
    from backend.core.event_bus import EventBus, EventType, Event
except ImportError as e:
    print(f"❌ 无法导入必要模块: {e}")
    print("请检查项目路径配置")
    sys.exit(1)


class CoreTester:
    """Core 模块测试类 - 分阶段测试核心功能"""
    
    def __init__(self):
        self.test_results = []
        self.event_bus = None
        self.received_events = []
    
    def test_message_system(self) -> bool:
        """
        阶段 1: Message 消息系统测试
        
        测试内容：
        - 创建基本消息
        - 创建专用消息类型
        - 消息转换为字典
        - 消息元数据
        """
        print("\n" + "="*60)
        print("阶段 1: Message 消息系统测试")
        print("="*60)
        
        try:
            # 测试 1.1: 创建基本消息
            print("\n[1.1] 创建基本消息...")
            msg = Message(content="Hello", role="user")
            assert msg.content == "Hello"
            assert msg.role == "user"
            assert msg.timestamp is not None
            print(f"✅ 基本消息创建成功: {msg}")
            
            # 测试 1.2: 创建专用消息类型
            print("\n[1.2] 创建专用消息类型...")
            system_msg = SystemMessage("You are a helpful assistant")
            user_msg = UserMessage("What is Python?")
            assistant_msg = AssistantMessage("Python is a programming language")
            
            assert system_msg.role == "system"
            assert user_msg.role == "user"
            assert assistant_msg.role == "assistant"
            print("✅ 专用消息类型创建成功")
            print(f"   - SystemMessage: {system_msg.content[:30]}...")
            print(f"   - UserMessage: {user_msg.content}")
            print(f"   - AssistantMessage: {assistant_msg.content[:30]}...")
            
            # 测试 1.3: 消息转换为字典
            print("\n[1.3] 消息转换为字典...")
            msg_dict = user_msg.to_dict()
            assert "role" in msg_dict
            assert "content" in msg_dict
            assert msg_dict["role"] == "user"
            print(f"✅ 消息字典转换成功: {msg_dict}")
            
            # 测试 1.4: 消息元数据
            print("\n[1.4] 测试消息元数据...")
            meta_msg = Message(
                content="Test message",
                role="user",
                metadata={"source": "test", "priority": "high"}
            )
            assert meta_msg.metadata is not None
            assert meta_msg.metadata.get("source") == "test"
            print(f"✅ 消息元数据功能正常: {meta_msg.metadata}")
            
            # 测试 1.5: 消息列表转换（用于 LLM API）
            print("\n[1.5] 消息列表转换...")
            messages = [system_msg, user_msg, assistant_msg]
            dict_messages = [msg.to_dict() for msg in messages]
            assert len(dict_messages) == 3
            assert all("role" in d and "content" in d for d in dict_messages)
            print(f"✅ 消息列表转换成功 ({len(dict_messages)} 条消息)")
            
            print("\n✅ 阶段 1 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 1 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_tool_system(self) -> bool:
        """
        阶段 2: Tool 工具基类测试
        
        测试内容：
        - 创建自定义工具
        - 工具参数定义
        - 工具执行
        - 工具序列化
        """
        print("\n" + "="*60)
        print("阶段 2: Tool 工具基类测试")
        print("="*60)
        
        try:
            # 定义测试工具
            class CalculatorTool(Tool):
                """简单的计算器工具"""
                
                def __init__(self):
                    super().__init__(
                        name="calculator",
                        description="执行基本数学计算"
                    )
                
                def get_parameters(self) -> List[ToolParameter]:
                    return [
                        ToolParameter(
                            name="operation",
                            type="string",
                            description="运算类型 (add/subtract/multiply/divide)",
                            required=True
                        ),
                        ToolParameter(
                            name="a",
                            type="number",
                            description="第一个数字",
                            required=True
                        ),
                        ToolParameter(
                            name="b",
                            type="number",
                            description="第二个数字",
                            required=True
                        )
                    ]
                
                def run(self, parameters: Dict[str, Any]) -> str:
                    operation = parameters.get("operation")
                    a = float(parameters.get("a", 0))
                    b = float(parameters.get("b", 0))
                    
                    if operation == "add":
                        result = a + b
                    elif operation == "subtract":
                        result = a - b
                    elif operation == "multiply":
                        result = a * b
                    elif operation == "divide":
                        if b == 0:
                            return "错误: 除数不能为零"
                        result = a / b
                    else:
                        return f"错误: 不支持的运算类型 {operation}"
                    
                    return f"{a} {operation} {b} = {result}"
            
            # 测试 2.1: 创建工具实例
            print("\n[2.1] 创建工具实例...")
            calc = CalculatorTool()
            assert calc.name == "calculator"
            assert calc.description == "执行基本数学计算"
            print(f"✅ 工具实例创建成功: {calc.name}")
            
            # 测试 2.2: 获取参数定义
            print("\n[2.2] 获取工具参数定义...")
            params = calc.get_parameters()
            assert len(params) == 3
            assert all(isinstance(p, ToolParameter) for p in params)
            print(f"✅ 参数定义获取成功 ({len(params)} 个参数):")
            for p in params:
                req = "必填" if p.required else "可选"
                print(f"   - {p.name} ({p.type}, {req}): {p.description}")
            
            # 测试 2.3: 执行工具 - 加法
            print("\n[2.3] 执行工具 - 加法...")
            result = calc.run({"operation": "add", "a": 10, "b": 5})
            assert "15" in result
            print(f"✅ 加法计算成功: {result}")
            
            # 测试 2.4: 执行工具 - 除法
            print("\n[2.4] 执行工具 - 除法...")
            result = calc.run({"operation": "divide", "a": 20, "b": 4})
            assert "5" in result
            print(f"✅ 除法计算成功: {result}")
            
            # 测试 2.5: 工具序列化（用于传递给 LLM）
            print("\n[2.5] 工具序列化...")
            tool_dict = {
                "name": calc.name,
                "description": calc.description,
                "parameters": [
                    {
                        "name": p.name,
                        "type": p.type,
                        "description": p.description,
                        "required": p.required
                    }
                    for p in calc.get_parameters()
                ]
            }
            assert tool_dict["name"] == "calculator"
            assert len(tool_dict["parameters"]) == 3
            print(f"✅ 工具序列化成功")
            
            print("\n✅ 阶段 2 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 2 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_event_bus(self) -> bool:
        """
        阶段 3: EventBus 事件总线测试
        
        测试内容：
        - 创建事件总线
        - 订阅事件
        - 发布事件
        - 多个订阅者
        - 事件数据传递
        """
        print("\n" + "="*60)
        print("阶段 3: EventBus 事件总线测试")
        print("="*60)
        
        try:
            # 测试 3.1: 创建事件总线（单例模式）
            print("\n[3.1] 创建事件总线...")
            bus1 = EventBus()
            bus2 = EventBus()
            assert bus1 is bus2, "EventBus 应该是单例"
            print("✅ 事件总线单例创建成功")
            
            self.event_bus = bus1
            self.received_events = []
            
            # 定义事件处理器
            async def on_chat_received(event: Event):
                """处理聊天接收事件"""
                self.received_events.append(("chat_received", event.data))
                print(f"   [Handler 1] 收到聊天消息: {event.data.get('message', 'N/A')}")
            
            async def on_chat_received_2(event: Event):
                """第二个聊天接收处理器"""
                self.received_events.append(("chat_received_2", event.data))
                print(f"   [Handler 2] 也收到了: {event.data.get('message', 'N/A')}")
            
            async def on_system_startup(event: Event):
                """处理系统启动事件"""
                self.received_events.append(("system_startup", event.data))
                print(f"   [Handler] 系统启动: {event.data}")
            
            # 测试 3.2: 订阅事件
            print("\n[3.2] 订阅事件...")
            self.event_bus.subscribe(EventType.CHAT_RECEIVED, on_chat_received)
            self.event_bus.subscribe(EventType.CHAT_RECEIVED, on_chat_received_2)
            self.event_bus.subscribe(EventType.SYSTEM_STARTUP, on_system_startup)
            print("✅ 事件订阅成功 (2 个 CHAT_RECEIVED + 1 个 SYSTEM_STARTUP)")
            
            # 测试 3.3: 发布事件
            print("\n[3.3] 发布 CHAT_RECEIVED 事件...")
            await self.event_bus.publish(
                EventType.CHAT_RECEIVED,
                {"message": "Hello, World!", "user": "test_user"}
            )
            # 等待异步处理完成
            await asyncio.sleep(0.1)
            
            # 验证两个处理器都收到了事件
            chat_events = [e for e in self.received_events if "chat_received" in e[0]]
            assert len(chat_events) == 2, f"应该有2个聊天事件，实际有 {len(chat_events)}"
            print(f"✅ 事件发布成功，{len(chat_events)} 个处理器收到事件")
            
            # 测试 3.4: 发布不同类型的事件
            print("\n[3.4] 发布 SYSTEM_STARTUP 事件...")
            await self.event_bus.publish(
                EventType.SYSTEM_STARTUP,
                {"version": "1.0.0", "timestamp": datetime.now().isoformat()}
            )
            await asyncio.sleep(0.1)
            
            startup_events = [e for e in self.received_events if e[0] == "system_startup"]
            assert len(startup_events) == 1
            print("✅ 系统启动事件发布成功")
            
            # 测试 3.5: 事件数据验证
            print("\n[3.5] 验证事件数据...")
            chat_data = chat_events[0][1]
            assert chat_data["message"] == "Hello, World!"
            assert chat_data["user"] == "test_user"
            print(f"✅ 事件数据验证成功: {chat_data}")
            
            # 测试 3.6: 未订阅的事件（不应该报错）
            print("\n[3.6] 发布未订阅的事件...")
            await self.event_bus.publish(
                EventType.TASK_COMPLETED,
                {"task_id": "test_123"}
            )
            await asyncio.sleep(0.1)
            print("✅ 未订阅事件处理正常（无错误）")
            
            print("\n✅ 阶段 3 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 3 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_logger_system(self) -> bool:
        """
        阶段 4: Logger 日志系统测试
        
        测试内容：
        - 基本日志记录
        - 不同日志级别
        - 日志格式
        """
        print("\n" + "="*60)
        print("阶段 4: Logger 日志系统测试")
        print("="*60)
        
        try:
            # 测试 4.1: 创建测试日志器
            print("\n[4.1] 创建测试日志器...")
            test_logger = logging.getLogger("test_core_module")
            test_logger.setLevel(logging.DEBUG)
            print("✅ 测试日志器创建成功")
            
            # 测试 4.2: 不同级别的日志
            print("\n[4.2] 测试不同级别的日志...")
            test_logger.debug("这是 DEBUG 消息")
            test_logger.info("这是 INFO 消息")
            test_logger.warning("这是 WARNING 消息")
            test_logger.error("这是 ERROR 消息")
            print("✅ 不同级别日志记录成功")
            
            # 测试 4.3: 带变量的日志
            print("\n[4.3] 测试带变量的日志...")
            user = "test_user"
            count = 42
            test_logger.info(f"用户 {user} 执行了 {count} 次操作")
            print("✅ 变量日志记录成功")
            
            print("\n✅ 阶段 4 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 4 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False


async def main():
    """主测试函数"""
    print("="*60)
    print("🚀 Core 核心模块测试")
    print("="*60)
    
    tester = CoreTester()
    
    try:
        # 按顺序执行测试
        tests = [
            ("Message 消息系统", tester.test_message_system),
            ("Tool 工具基类", tester.test_tool_system),
        ]
        
        async_tests = [
            ("EventBus 事件总线", tester.test_event_bus),
        ]
        
        sync_tests = [
            ("Logger 日志系统", tester.test_logger_system),
        ]
        
        results = []
        
        # 执行同步测试
        for test_name, test_func in tests:
            result = test_func()
            results.append((test_name, result))
        
        # 执行异步测试
        for test_name, test_func in async_tests:
            result = await test_func()
            results.append((test_name, result))
        
        # 执行额外的同步测试
        for test_name, test_func in sync_tests:
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
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(1)
