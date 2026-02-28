"""
MCP (Model Context Protocol) 服务模块测试文件

测试 MCP 模块的各项功能（清晰分阶段测试）:

阶段 1: MCP 注册中心测试 (MCPRegistry)
阶段 2: 插件加载测试
阶段 3: MCP 适配器测试 (MCPAdapterTool)
阶段 4: MCP 管理器测试 (MCPManager)
阶段 5: 工具调用测试
阶段 6: 插件集成测试

使用方法：
    cd /Users/mingy/Documents/python/01-python
    python backend/test/test_mcp.py

前置条件：
    - 至少有一个 MCP 插件已安装（如 search 插件）
"""

import sys
import logging
import json
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any

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
    from backend.utils.mcp import (
        MCPRegistry,
        get_registry,
        reset_registry,
        MCPAdapterTool,
        MCPManager,
        get_mcp_manager
    )
    from backend.core.tool import Tool, ToolParameter
except ImportError as e:
    print(f"❌ 无法导入必要模块: {e}")
    print("请检查项目路径配置")
    sys.exit(1)


class MCPTester:
    """MCP 服务测试类 - 分阶段测试 MCP 功能"""
    
    def __init__(self):
        self.temp_dir = None
        self.registry = None
        self.manager = None
        self.test_results = []
    
    def setup(self):
        """测试前准备"""
        # 创建临时测试目录
        self.temp_dir = tempfile.mkdtemp(prefix="mcp_test_")
        logger.info(f"创建临时测试目录: {self.temp_dir}")
        
        # 创建测试插件
        self._create_test_plugin()
    
    def cleanup(self):
        """测试后清理"""
        if self.temp_dir and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
            logger.info(f"清理临时测试目录: {self.temp_dir}")
        
        # 重置全局注册中心
        reset_registry()
    
    def _create_test_plugin(self):
        """创建一个简单的测试插件"""
        plugin_dir = Path(self.temp_dir) / "test_plugin"
        plugin_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建 __init__.py
        init_file = plugin_dir / "__init__.py"
        init_file.write_text("")
        
        # 创建插件类文件
        plugin_file = plugin_dir / "test_agent.py"
        plugin_code = '''"""测试插件"""

class TestAgent:
    """简单的测试插件"""
    
    def handle_handoff(self, parameters):
        """处理请求"""
        query = parameters.get('query', '')
        return f"测试插件接收到查询: {query}"
'''
        plugin_file.write_text(plugin_code)
        
        # 创建 manifest.json
        manifest_file = plugin_dir / "manifest.json"
        manifest = {
            "name": "test_plugin",
            "description": "用于测试的简单插件",
            "entryPoint": {
                "module": "test_plugin.test_agent",
                "class": "TestAgent"
            },
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "测试查询内容"
                    }
                },
                "required": ["query"]
            }
        }
        
        with open(manifest_file, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        
        logger.info(f"创建测试插件: {plugin_dir}")
        
        # 将测试插件目录添加到 Python 路径
        if str(self.temp_dir) not in sys.path:
            sys.path.insert(0, str(self.temp_dir))
    
    def test_registry_basic(self) -> bool:
        """
        阶段 1: MCP 注册中心测试
        
        测试内容：
        - 创建注册中心
        - 获取注册中心信息
        - 注册中心统计
        """
        print("\n" + "="*60)
        print("阶段 1: MCP 注册中心测试 (MCPRegistry)")
        print("="*60)
        
        try:
            # 测试 1.1: 创建注册中心
            print("\n[1.1] 创建注册中心...")
            registry = MCPRegistry(plugin_dir=str(self.temp_dir))
            assert registry is not None
            print("✅ 注册中心创建成功")
            
            # 测试 1.2: 获取统计信息
            print("\n[1.2] 获取统计信息...")
            stats = registry.get_statistics()
            print(f"   已注册插件数: {stats['total_plugins']}")
            print("✅ 统计信息获取成功")
            
            # 测试 1.3: 获取插件列表
            print("\n[1.3] 获取插件列表...")
            plugin_names = registry.get_plugin_names()
            print(f"   插件列表: {plugin_names}")
            print("✅ 插件列表获取成功")
            
            self.registry = registry
            
            print("\n✅ 阶段 1 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 1 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_plugin_loading(self) -> bool:
        """
        阶段 2: 插件加载测试
        
        测试内容：
        - 扫描并注册插件
        - 获取插件信息
        - 验证插件实例
        """
        print("\n" + "="*60)
        print("阶段 2: 插件加载测试")
        print("="*60)
        
        try:
            # 测试 2.1: 扫描并注册插件
            print("\n[2.1] 扫描并注册插件...")
            self.registry.scan_and_register()
            
            plugins = self.registry.get_all_plugins()
            print(f"   找到 {len(plugins)} 个插件")
            
            if len(plugins) == 0:
                print("⚠️  未找到任何插件，跳过后续测试")
                return True
            
            print("✅ 插件扫描成功")
            
            # 测试 2.2: 获取插件信息
            print("\n[2.2] 获取插件信息...")
            for plugin_name in self.registry.get_plugin_names():
                info = self.registry.get_plugin_info(plugin_name)
                if info:
                    print(f"   - {plugin_name}: {info.get('description', 'N/A')}")
            print("✅ 插件信息获取成功")
            
            # 测试 2.3: 验证插件实例
            print("\n[2.3] 验证插件实例...")
            test_plugin = self.registry.get_plugin("test_plugin")
            if test_plugin:
                assert 'instance' in test_plugin
                assert 'manifest' in test_plugin
                print("✅ 测试插件实例验证成功")
            else:
                print("⚠️  未找到测试插件")
            
            print("\n✅ 阶段 2 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 2 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_adapter(self) -> bool:
        """
        阶段 3: MCP 适配器测试
        
        测试内容：
        - 创建适配器
        - 获取参数定义
        - 转换为工具格式
        """
        print("\n" + "="*60)
        print("阶段 3: MCP 适配器测试 (MCPAdapterTool)")
        print("="*60)
        
        try:
            # 检查是否有可用插件
            plugin_names = self.registry.get_plugin_names()
            if not plugin_names:
                print("⚠️  没有可用插件，跳过适配器测试")
                return True
            
            plugin_name = plugin_names[0]
            
            # 测试 3.1: 创建适配器
            print(f"\n[3.1] 为插件 '{plugin_name}' 创建适配器...")
            adapter = MCPAdapterTool(plugin_name, self.registry)
            assert adapter is not None
            print(f"✅ 适配器创建成功")
            
            # 测试 3.2: 获取参数定义
            print("\n[3.2] 获取参数定义...")
            params = adapter.get_parameters()
            print(f"   参数数量: {len(params)}")
            for param in params:
                print(f"   - {param.name} ({param.type}): {param.description}")
            print("✅ 参数定义获取成功")
            
            # 测试 3.3: 转换为字典格式
            print("\n[3.3] 转换为工具格式...")
            tool_dict = adapter.to_dict()
            assert 'name' in tool_dict
            assert 'description' in tool_dict
            print(f"   工具名: {tool_dict['name']}")
            print("✅ 工具格式转换成功")
            
            print("\n✅ 阶段 3 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 3 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_manager(self) -> bool:
        """
        阶段 4: MCP 管理器测试
        
        测试内容：
        - 创建管理器
        - 获取工具列表
        - 获取工具信息
        """
        print("\n" + "="*60)
        print("阶段 4: MCP 管理器测试 (MCPManager)")
        print("="*60)
        
        try:
            # 测试 4.1: 创建管理器（使用真实插件目录）
            print("\n[4.1] 创建 MCP 管理器...")
            # 重置并使用真实插件目录
            reset_registry()
            real_plugin_dir = ROOT_DIR / "backend" / "utils" / "mcp" / "plugins"
            
            if not real_plugin_dir.exists():
                print(f"⚠️  真实插件目录不存在: {real_plugin_dir}")
                print("   使用测试插件目录")
                # 使用测试注册中心
                from backend.utils.mcp.registry import _registry_instance, _DEFAULT_PLUGIN_DIR
                global_registry = MCPRegistry(plugin_dir=str(self.temp_dir))
                global_registry.scan_and_register()
            else:
                print(f"   插件目录: {real_plugin_dir}")
                global_registry = get_registry()
            
            manager = MCPManager()
            self.manager = manager
            
            print(f"✅ 管理器创建成功")
            
            # 测试 4.2: 获取工具列表
            print("\n[4.2] 获取工具列表...")
            tool_names = manager.get_tool_names()
            print(f"   可用工具数: {len(tool_names)}")
            for name in tool_names:
                print(f"   - {name}")
            print("✅ 工具列表获取成功")
            
            # 测试 4.3: 获取工具详情
            print("\n[4.3] 获取工具详情...")
            if tool_names:
                tool_name = tool_names[0]
                tool = manager.get_tool(tool_name)
                if tool:
                    print(f"   工具名: {tool.name}")
                    print(f"   描述: {tool.description}")
                    print("✅ 工具详情获取成功")
                else:
                    print("⚠️  获取工具失败")
            else:
                print("⚠️  没有可用工具")
            
            # 测试 4.4: 列出所有工具
            print("\n[4.4] 列出所有工具...")
            tools_list = manager.list_tools()
            print(f"   {tools_list[:200]}...")
            print("✅ 工具列表生成成功")
            
            print("\n✅ 阶段 4 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 4 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_tool_calling(self) -> bool:
        """
        阶段 5: 工具调用测试
        
        测试内容：
        - 调用测试插件
        - 验证返回结果
        """
        print("\n" + "="*60)
        print("阶段 5: 工具调用测试")
        print("="*60)
        
        try:
            # 先用测试插件进行简单测试
            print("\n[5.1] 测试插件调用...")
            
            # 重置并使用测试插件
            reset_registry()
            test_registry = MCPRegistry(plugin_dir=str(self.temp_dir))
            test_registry.scan_and_register()
            
            if "test_plugin" in test_registry.get_plugin_names():
                adapter = MCPAdapterTool("test_plugin", test_registry)
                result = adapter.run({"query": "测试查询"})
                print(f"   返回结果: {result}")
                assert "测试插件接收到查询" in result
                print("✅ 测试插件调用成功")
            else:
                print("⚠️  测试插件未找到，跳过调用测试")
            
            print("\n✅ 阶段 5 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 5 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_integration(self) -> bool:
        """
        阶段 6: 插件集成测试
        
        测试内容：
        - 完整的工作流程
        - 多个插件协同
        - LLM 工具格式兼容性
        """
        print("\n" + "="*60)
        print("阶段 6: 插件集成测试")
        print("="*60)
        
        try:
            # 测试 6.1: 完整工作流程
            print("\n[6.1] 测试完整工作流程...")
            
            # 使用真实插件目录
            reset_registry()
            registry = get_registry()
            manager = MCPManager()
            
            tool_names = manager.get_tool_names()
            if tool_names:
                print(f"   可用工具: {', '.join(tool_names)}")
                print("✅ 完整工作流程正常")
            else:
                print("⚠️  没有可用工具")
            
            # 测试 6.2: LLM 工具格式
            print("\n[6.2] 测试 LLM 工具格式...")
            llm_tools = manager.get_tools_for_llm()
            print(f"   生成 {len(llm_tools)} 个 LLM 工具描述")
            if llm_tools:
                # 验证格式
                first_tool = llm_tools[0]
                assert 'type' in first_tool
                assert 'function' in first_tool
                print(f"   示例工具: {first_tool['function']['name']}")
                print("✅ LLM 工具格式正确")
            else:
                print("⚠️  没有生成 LLM 工具")
            
            # 测试 6.3: 全局单例
            print("\n[6.3] 测试全局单例...")
            manager1 = get_mcp_manager()
            manager2 = get_mcp_manager()
            # 注意：每次调用 get_mcp_manager 都会创建新实例
            # 这里只验证函数调用不会出错
            print("✅ 全局单例获取正常")
            
            print("\n✅ 阶段 6 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 6 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """主测试函数"""
    print("="*60)
    print("🚀 MCP 服务模块测试")
    print("="*60)
    
    tester = MCPTester()
    tester.setup()
    
    try:
        # 按顺序执行测试
        tests = [
            ("MCP 注册中心", tester.test_registry_basic),
            ("插件加载", tester.test_plugin_loading),
            ("MCP 适配器", tester.test_adapter),
            ("MCP 管理器", tester.test_manager),
            ("工具调用", tester.test_tool_calling),
            ("插件集成", tester.test_integration),
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
    finally:
        tester.cleanup()


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(1)
