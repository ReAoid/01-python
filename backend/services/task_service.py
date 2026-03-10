"""
任务服务 (TaskService)

负责执行后台任务，支持：
1. 一次性任务执行 (TriggerType.ONCE)
2. 定时任务创建和管理
3. 工具链调用
"""

import logging
import asyncio
import json
from typing import Optional, Dict, Any, List
from datetime import datetime

from backend.core.event_bus import event_bus, Event, EventType
from backend.core.message import Message
from backend.services.llm_service import get_llm
from backend.utils.skills.loader import get_skill_loader
from backend.utils.llm.tool_chain_handler import ToolChainHandler
from backend.utils.scheduler.models import (
    TaskConfig, TriggerConfig, TriggerType, ExecutorConfig, ExecutorType
)
from backend.utils.scheduler.scheduler import get_scheduler
from backend.config.prompts import SYSTEM_PROMPT_TASK_EXECUTOR

logger = logging.getLogger(__name__)


class TaskService:
    """
    任务服务
    
    负责：
    1. 分析用户意图，识别任务类型
    2. 执行一次性任务（TriggerType.ONCE）
    3. 创建定时任务
    4. 管理工具链执行
    """
    
    def __init__(self):
        self.llm = get_llm()
        self.skill_loader = get_skill_loader()
        self.scheduler = get_scheduler()
        
        # 使用统一的 ToolChainHandler
        self.tool_chain_handler = ToolChainHandler(self.llm, max_iterations=10)
        
        # 加载 task skill
        self.skill_prompt = self._build_skill_prompt()
        
        # 订阅事件
        event_bus.subscribe(EventType.CHAT_COMPLETED, self.handle_chat_analysis)
        
        logger.info("任务服务已初始化")
    
    def _build_skill_prompt(self) -> str:
        """构建 skill 提示词"""
        skill_content = self.skill_loader.get_skill_prompt("task")
        if skill_content:
            return f"{SYSTEM_PROMPT_TASK_EXECUTOR}\n\n{skill_content}"
        return SYSTEM_PROMPT_TASK_EXECUTOR
    
    async def handle_chat_analysis(self, event: Event):
        """处理聊天完成事件，分析是否有任务需要执行"""
        user_content = event.data.get("user_content")
        ai_content = event.data.get("ai_content", "")
        
        if not user_content:
            return
        
        # 检查 AI 回复中是否有任务委派
        task_info = self._parse_task_delegation(ai_content)
        if task_info:
            await self._handle_delegated_task(task_info)
    
    def _parse_task_delegation(self, ai_content: str) -> Optional[Dict[str, Any]]:
        """解析 AI 回复中的任务委派信息"""
        try:
            # 尝试从 AI 回复中提取 JSON 格式的任务委派
            if "delegate_to" in ai_content and "task_service" in ai_content:
                # 简单的 JSON 提取
                start = ai_content.find('{')
                end = ai_content.rfind('}') + 1
                if start != -1 and end > start:
                    json_str = ai_content[start:end]
                    return json.loads(json_str)
        except Exception as e:
            logger.debug(f"解析任务委派失败: {e}")
        return None
    
    async def _handle_delegated_task(self, task_info: Dict[str, Any]):
        """处理委派的任务"""
        task_type = task_info.get("task_type", "once")
        task_description = task_info.get("task_description", "")
        
        if task_type == "scheduled":
            # 创建定时任务
            task_config = task_info.get("task_config", {})
            await self.create_scheduled_task(task_description, task_config)
        else:
            # 执行一次性任务
            await self.execute_once_task(task_description)
    
    async def execute_once_task(self, task_description: str) -> str:
        """
        执行一次性任务 (TriggerType.ONCE)
        
        Args:
            task_description: 任务描述
            
        Returns:
            执行结果
        """
        logger.info(f"开始执行一次性任务: {task_description[:50]}...")
        
        try:
            # 构建消息
            system_msg = Message(role="system", content=self.skill_prompt)
            messages = [Message(role="user", content=task_description)]
            
            # 使用统一的 ToolChainHandler 执行任务
            result = await self.tool_chain_handler.execute(
                messages=messages,
                system_message=system_msg
            )
            
            # 发布任务完成事件
            await event_bus.publish(EventType.TASK_COMPLETED, {
                "result": result,
                "original_task": task_description,
                "task_type": "once"
            })
            
            logger.info(f"一次性任务执行完成")
            return result
            
        except Exception as e:
            error_msg = f"任务执行失败: {str(e)}"
            logger.error(error_msg)
            
            await event_bus.publish(EventType.TASK_COMPLETED, {
                "result": error_msg,
                "original_task": task_description,
                "task_type": "once",
                "error": True
            })
            
            return error_msg
    
    async def create_scheduled_task(
        self,
        task_description: str,
        task_config: Dict[str, Any]
    ) -> Optional[str]:
        """
        创建定时任务
        
        Args:
            task_description: 任务描述
            task_config: 任务配置
            
        Returns:
            任务 ID 或 None
        """
        logger.info(f"创建定时任务: {task_description[:50]}...")
        
        try:
            # 构建 TaskConfig
            trigger_config = task_config.get("trigger", {})
            executor_config = task_config.get("executor", {})
            
            config = TaskConfig(
                name=task_config.get("name", task_description[:50]),
                description=task_description,
                trigger=TriggerConfig(**trigger_config),
                executor=ExecutorConfig(**executor_config),
                priority=task_config.get("priority", 5),
                timeout_seconds=task_config.get("timeout_seconds", 3600)
            )
            
            # 注册到调度器
            task_id = self.scheduler.register_task(config)
            
            # 发布任务创建事件
            await event_bus.publish(EventType.TASK_COMPLETED, {
                "result": f"定时任务已创建，ID: {task_id}",
                "original_task": task_description,
                "task_type": "scheduled",
                "task_id": task_id
            })
            
            logger.info(f"定时任务创建成功: {task_id}")
            return task_id
            
        except Exception as e:
            error_msg = f"创建定时任务失败: {str(e)}"
            logger.error(error_msg)
            return None
    
    async def execute_task_by_id(self, task_id: str) -> Optional[str]:
        """
        手动触发执行指定任务
        
        Args:
            task_id: 任务 ID
            
        Returns:
            执行结果或 None
        """
        record = self.scheduler.trigger_task(task_id)
        if record:
            return record.result
        return None
    
    def list_tasks(self) -> List[Dict[str, Any]]:
        """列出所有任务"""
        tasks = self.scheduler.list_tasks()
        return [
            {
                "task_id": t.task_id,
                "name": t.name,
                "description": t.description,
                "status": t.status.value,
                "trigger_type": t.trigger.type.value
            }
            for t in tasks
        ]


# 全局单例
_task_service_instance: Optional[TaskService] = None


def get_task_service() -> TaskService:
    """获取全局 TaskService 单例"""
    global _task_service_instance
    if _task_service_instance is None:
        _task_service_instance = TaskService()
    return _task_service_instance
