"""
MCP 注册中心
负责扫描和加载插件
"""

import json
import importlib
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

class MCPRegistry:
    """MCP 插件注册中心"""

    def __init__(self, plugin_dir: str = "backend/utils/mcp/plugins"):
        self.plugin_dir = plugin_dir
        self.registry: Dict[str, Dict[str, Any]] = {}
        self.manifest_cache: Dict[str, Dict[str, Any]] = {}

    def scan_and_register(self):
        """扫描插件目录并自动注册所有插件"""
        plugin_path = Path(self.plugin_dir)

        if not plugin_path.exists():
            logger.warning(f"插件目录不存在: {self.plugin_dir}")
            return

        # 查找所有 manifest.json 文件
        manifest_files = list(plugin_path.glob("**/manifest.json"))

        if not manifest_files:
            logger.warning(f"未找到任何 manifest.json 文件在目录: {self.plugin_dir}")
            return

        logger.info(f"开始扫描插件目录: {self.plugin_dir}, 找到 {len(manifest_files)} 个插件")
        for manifest_file in manifest_files:
            try:
                self._load_plugin(manifest_file)
            except Exception as e:
                logger.exception(f"加载插件失败 {manifest_file}: {e}")

    def _load_plugin(self, manifest_path: Path):
        """加载单个插件"""
        try:
            # 读取 manifest 文件
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)

            plugin_name = manifest.get('name')
            if not plugin_name:
                logger.error(f"Manifest 缺少 'name' 字段: {manifest_path}")
                return

            # 获取入口点配置
            entry_point = manifest.get('entryPoint', {})
            module_name = entry_point.get('module')
            class_name = entry_point.get('class')

            if not module_name or not class_name:
                logger.error(f"Manifest 缺少 entryPoint 配置: {plugin_name}")
                return

            # 动态导入模块
            try:
                module = importlib.import_module(module_name)
            except ImportError as e:
                logger.error(f"无法导入模块 {module_name}: {e}")
                return

            # 获取类并实例化
            try:
                plugin_class = getattr(module, class_name)
                instance = plugin_class()
            except AttributeError:
                logger.error(f"模块 {module_name} 中未找到类 {class_name}")
                return
            except Exception as e:
                logger.error(f"实例化 {class_name} 失败: {e}")
                return

            # 注册到 registry
            self.registry[plugin_name] = {
                "instance": instance,
                "manifest": manifest,
                "module": module_name,
                "class": class_name
            }

            # 缓存 manifest
            self.manifest_cache[plugin_name] = manifest

            logger.info(f"成功注册 MCP 插件: {plugin_name}")

        except json.JSONDecodeError as e:
            logger.error(f"Manifest JSON 格式错误 {manifest_path}: {e}")
        except Exception as e:
            logger.exception(f"加载插件时发生未知错误 {manifest_path}")

    def get_plugin(self, name: str) -> Optional[Dict[str, Any]]:
        """获取指定名称的插件"""
        return self.registry.get(name)

    def get_all_plugins(self) -> Dict[str, Dict[str, Any]]:
        """获取所有已注册的插件"""
        return self.registry.copy()

    def get_plugin_names(self) -> List[str]:
        """获取所有插件名称"""
        return list(self.registry.keys())

    def get_plugin_info(self, name: str) -> Optional[Dict[str, Any]]:
        """获取插件详细信息"""
        if name not in self.registry:
            return None

        plugin = self.registry[name]
        manifest = plugin['manifest']

        return {
            "name": name,
            "description": manifest.get('description', ''),
            "input_schema": manifest.get('inputSchema', {})
        }

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_plugins": len(self.registry),
            "plugin_names": list(self.registry.keys())
        }


# 全局单例
_registry_instance: Optional[MCPRegistry] = None

# 默认插件目录（使用绝对路径）
import os
_DEFAULT_PLUGIN_DIR = os.path.join(
    os.path.dirname(__file__),
    "plugins"
)


def get_registry() -> MCPRegistry:
    """
    获取全局 Registry 单例
    
    使用固定的插件目录: backend/utils/mcp/plugins
    这是一个真正的单例，不接受参数，每次都返回同一个实例
    """
    global _registry_instance
    
    if _registry_instance is None:
        _registry_instance = MCPRegistry(_DEFAULT_PLUGIN_DIR)
        _registry_instance.scan_and_register()
    
    return _registry_instance


def reset_registry():
    """重置 Registry 单例（主要用于测试）"""
    global _registry_instance
    _registry_instance = None
