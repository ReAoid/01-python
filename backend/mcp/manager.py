"""
MCP 管理器
统一管理所有 MCP 插件和工具
"""

from typing import Dict, Any, List, Optional
from loguru import logger
from backend.mcp.registry import MCPRegistry, get_registry
from backend.mcp.adapter import MCPAdapterTool


class MCPManager:
    """MCP 管理器 - 统一的插件管理和调用入口"""

    def __init__(self):
        """
        初始化 MCP 管理器
        
        使用全局 Registry 单例加载插件
        """
        self.registry = get_registry()
        self.tools: Dict[str, MCPAdapterTool] = {}
        self._load_all_tools()

    def _load_all_tools(self):
        """加载所有插件为 Tool"""
        for plugin_name in self.registry.get_plugin_names():
            try:
                tool = MCPAdapterTool(plugin_name, self.registry)
                self.tools[plugin_name] = tool
                logger.success(f"加载工具: {plugin_name}")
            except Exception as e:
                logger.error(f"加载工具失败 {plugin_name}: {e}")

    def get_tool(self, name: str) -> Optional[MCPAdapterTool]:
        """获取指定名称的工具"""
        return self.tools.get(name)

    def get_all_tools(self) -> List[MCPAdapterTool]:
        """获取所有工具"""
        return list(self.tools.values())

    def get_tool_names(self) -> List[str]:
        """获取所有工具名称"""
        return list(self.tools.keys())

    def call_tool(self, tool_name: str, parameters: Dict[str, Any]) -> str:
        """
        调用指定工具
        
        Args:
            tool_name: 工具名称
            parameters: 工具参数
            
        Returns:
            工具执行结果
        """
        tool = self.get_tool(tool_name)
        if not tool:
            logger.error(f"未找到工具: {tool_name}")
            return f"错误: 未找到工具 {tool_name}"

        try:
            logger.info(f"调用工具: {tool_name}, 参数: {parameters}")
            result = tool.run(parameters)
            logger.debug(f"工具 {tool_name} 执行完成")
            return result
        except Exception as e:
            logger.exception(f"调用工具 {tool_name} 失败")
            return f"调用工具 {tool_name} 失败: {str(e)}"

    def list_tools(self) -> str:
        """列出所有可用工具的格式化描述"""
        if not self.tools:
            return "暂无可用工具"

        lines = ["可用工具列表:"]
        for name, tool in self.tools.items():
            lines.append(f"\n- {name}: {tool.description}")
            params = tool.get_parameters()
            if params:
                lines.append("  参数:")
                for param in params:
                    required = "必填" if param.required else "可选"
                    lines.append(f"    • {param.name} ({param.type}, {required}): {param.description}")

        return "\n".join(lines)

    def get_tools_for_llm(self) -> List[Dict[str, Any]]:
        """
        获取适合传递给 LLM 的工具描述格式
        通常用于 function calling
        """
        tools_desc = []
        for tool in self.tools.values():
            tool_dict = tool.to_dict()

            # 转换为 OpenAI function calling 格式
            properties = {}
            required = []

            for param in tool_dict['parameters']:
                properties[param['name']] = {
                    "type": param['type'],
                    "description": param['description']
                }
                if param['required']:
                    required.append(param['name'])

            tools_desc.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required
                    }
                }
            })

        return tools_desc

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_tools": len(self.tools),
            "tool_names": list(self.tools.keys()),
            "registry_stats": self.registry.get_statistics()
        }


# 全局单例
_manager_instance: Optional[MCPManager] = None

# 默认插件目录（使用绝对路径）
import os
_DEFAULT_PLUGIN_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "backend", "mcp", "plugins"
)


def get_mcp_manager(auto_setup_logger: bool = True) -> MCPManager:
    """
    获取全局 MCP Manager 单例
    
    使用固定的插件目录: backend/mcp/plugins
    这是一个真正的单例，不接受参数，每次都返回同一个实例
    
    Args:
        auto_setup_logger: 是否自动初始化日志配置 (默认 True)
    """
    global _manager_instance
    
    if _manager_instance is None:
        # 首次初始化时,自动配置日志
        if auto_setup_logger:
            from backend.core.logger import setup_logger
            setup_logger(log_level="INFO", log_file=None)
            logger.debug("MCP Manager 自动初始化日志配置")
        
        _manager_instance = MCPManager()
    
    return _manager_instance


def reset_mcp_manager():
    """重置 Manager 单例（主要用于测试）"""
    global _manager_instance
    _manager_instance = None
