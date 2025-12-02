"""
MCP (Model Context Protocol) 模块
提供插件化的工具系统
"""

from .registry import MCPRegistry, get_registry, reset_registry
from .adapter import MCPAdapterTool
from .manager import MCPManager, get_mcp_manager, reset_mcp_manager

__all__ = [
    'MCPRegistry', 'get_registry', 'reset_registry',
    'MCPAdapterTool',
    'MCPManager', 'get_mcp_manager', 'reset_mcp_manager'
]
