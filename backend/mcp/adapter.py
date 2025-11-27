"""
MCP 适配器
将 MCP 插件包装成标准的 Tool
"""

import asyncio
from typing import Dict, Any, List
from loguru import logger
from backend.core.tool import Tool, ToolParameter
from backend.mcp.registry import MCPRegistry


class MCPAdapterTool(Tool):
    """
    MCP 插件适配器
    将 MCP 插件包装成标准 Tool 接口
    """

    def __init__(self, plugin_name: str, registry: MCPRegistry):
        """
        初始化适配器
        
        Args:
            plugin_name: 插件名称
            registry: MCP 注册中心实例
        """
        plugin_info = registry.get_plugin(plugin_name)
        if not plugin_info:
            raise ValueError(f"插件 {plugin_name} 未找到")

        self.instance = plugin_info['instance']
        self.manifest = plugin_info['manifest']
        self.plugin_name = plugin_name

        # 从 manifest 获取基本信息
        name = self.manifest.get('name', plugin_name)
        description = self.manifest.get('description', '')

        super().__init__(name=name, description=description)

    def get_parameters(self) -> List[ToolParameter]:
        """从 manifest 的 inputSchema 生成参数定义"""
        params = []
        input_schema = self.manifest.get('inputSchema', {})
        properties = input_schema.get('properties', {})
        required_fields = input_schema.get('required', [])

        for param_name, param_config in properties.items():
            params.append(ToolParameter(
                name=param_name,
                type=param_config.get('type', 'string'),
                description=param_config.get('description', ''),
                required=(param_name in required_fields),
                default=param_config.get('default')
            ))

        return params

    def run(self, parameters: Dict[str, Any]) -> str:
        """
        执行 MCP 插件
        支持同步和异步方法
        """
        try:
            logger.debug(f"执行插件 {self.plugin_name}, 参数: {parameters}")
            
            # 优先查找 handle_handoff 方法 (NagaAgent 风格)
            if hasattr(self.instance, 'handle_handoff'):
                method = self.instance.handle_handoff

                # 检查是否为异步方法
                if asyncio.iscoroutinefunction(method):
                    # 异步方法: 需要在事件循环中运行
                    try:
                        loop = asyncio.get_running_loop()
                        # 如果已经在事件循环中,创建任务
                        future = asyncio.ensure_future(method(parameters))
                        return asyncio.get_event_loop().run_until_complete(future)
                    except RuntimeError:
                        # 没有运行中的事件循环,创建新的
                        return asyncio.run(method(parameters))
                else:
                    # 同步方法
                    return method(parameters)

            # 查找 handle 方法
            elif hasattr(self.instance, 'handle'):
                method = self.instance.handle

                if asyncio.iscoroutinefunction(method):
                    try:
                        loop = asyncio.get_running_loop()
                        future = asyncio.ensure_future(method(**parameters))
                        return asyncio.get_event_loop().run_until_complete(future)
                    except RuntimeError:
                        return asyncio.run(method(**parameters))
                else:
                    return method(**parameters)

            # 查找 run 方法
            elif hasattr(self.instance, 'run'):
                method = self.instance.run

                if asyncio.iscoroutinefunction(method):
                    try:
                        loop = asyncio.get_running_loop()
                        future = asyncio.ensure_future(method(**parameters))
                        return asyncio.get_event_loop().run_until_complete(future)
                    except RuntimeError:
                        return asyncio.run(method(**parameters))
                else:
                    return method(**parameters)

            else:
                error_msg = f"错误: 插件 {self.plugin_name} 未实现标准入口方法 (handle_handoff/handle/run)"
                logger.error(error_msg)
                return error_msg

        except Exception as e:
            logger.exception(f"执行插件 {self.plugin_name} 时出错")
            return f"执行插件 {self.plugin_name} 时出错: {str(e)}"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式,方便序列化"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "required": p.required,
                    "default": p.default
                }
                for p in self.get_parameters()
            ],
            "manifest": self.manifest
        }
