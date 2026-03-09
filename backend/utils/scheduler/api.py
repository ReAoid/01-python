"""
调度器 API 接口
供 AI 模型和外部系统调用的统一入口
"""

import json
from typing import Any, Dict, List, Optional
import logging

from backend.utils.scheduler.models import TaskConfig, TaskExecutionRecord
from backend.utils.scheduler.scheduler import get_scheduler
from backend.utils.scheduler.schema import validate_task_config, EXAMPLES

logger = logging.getLogger(__name__)


class SchedulerAPI:
    """
    调度器 API
    
    提供给 AI 模型的统一调用接口
    """
    
    def __init__(self):
        self.scheduler = get_scheduler()
    
    def execute(self, action: str, **kwargs) -> Dict[str, Any]:
        """
        执行调度器操作
        
        Args:
            action: 操作类型
            **kwargs: 操作参数
        
        Returns:
            操作结果
        """
        try:
            if action == "create_task":
                return self._create_task(kwargs.get("task_config", {}))
            
            elif action == "delete_task":
                return self._delete_task(kwargs.get("task_id"))
            
            elif action == "pause_task":
                return self._pause_task(kwargs.get("task_id"))
            
            elif action == "resume_task":
                return self._resume_task(kwargs.get("task_id"))
            
            elif action == "trigger_task":
                return self._trigger_task(kwargs.get("task_id"))
            
            elif action == "get_task":
                return self._get_task(kwargs.get("task_id"))
            
            elif action == "list_tasks":
                return self._list_tasks()
            
            elif action == "get_status":
                return self._get_status(kwargs.get("task_id"))
            
            elif action == "get_history":
                return self._get_history(
                    kwargs.get("task_id"),
                    kwargs.get("limit", 100)
                )
            
            elif action == "get_examples":
                return self._get_examples()
            
            elif action == "start_scheduler":
                return self._start_scheduler()
            
            elif action == "stop_scheduler":
                return self._stop_scheduler()
            
            elif action == "get_scheduler_stats":
                return self._get_scheduler_stats()
            
            else:
                return {
                    "success": False,
                    "error": f"未知操作: {action}",
                    "available_actions": [
                        "create_task", "delete_task", "pause_task", "resume_task",
                        "trigger_task", "get_task", "list_tasks", "get_status",
                        "get_history", "get_examples", "start_scheduler", 
                        "stop_scheduler", "get_scheduler_stats"
                    ]
                }
        
        except Exception as e:
            logger.exception(f"执行操作 {action} 失败")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _create_task(self, config: dict) -> Dict[str, Any]:
        """创建任务"""
        # 验证配置
        valid, error = validate_task_config(config)
        if not valid:
            return {
                "success": False,
                "error": f"配置验证失败: {error}"
            }
        
        # 创建任务
        task = TaskConfig(**config)
        task_id = self.scheduler.register_task(task)
        
        return {
            "success": True,
            "task_id": task_id,
            "message": f"任务 {task.name} 创建成功"
        }
    
    def _delete_task(self, task_id: str) -> Dict[str, Any]:
        """删除任务"""
        if not task_id:
            return {"success": False, "error": "缺少 task_id"}
        
        success = self.scheduler.unregister_task(task_id)
        return {
            "success": success,
            "message": f"任务 {task_id} 已删除" if success else f"任务 {task_id} 不存在"
        }
    
    def _pause_task(self, task_id: str) -> Dict[str, Any]:
        """暂停任务"""
        if not task_id:
            return {"success": False, "error": "缺少 task_id"}
        
        success = self.scheduler.pause_task(task_id)
        return {
            "success": success,
            "message": f"任务 {task_id} 已暂停" if success else f"任务 {task_id} 不存在"
        }
    
    def _resume_task(self, task_id: str) -> Dict[str, Any]:
        """恢复任务"""
        if not task_id:
            return {"success": False, "error": "缺少 task_id"}
        
        success = self.scheduler.resume_task(task_id)
        return {
            "success": success,
            "message": f"任务 {task_id} 已恢复" if success else f"任务 {task_id} 不存在"
        }
    
    def _trigger_task(self, task_id: str) -> Dict[str, Any]:
        """手动触发任务"""
        if not task_id:
            return {"success": False, "error": "缺少 task_id"}
        
        record = self.scheduler.trigger_task(task_id)
        if record:
            return {
                "success": True,
                "record": {
                    "record_id": record.record_id,
                    "status": record.status.value,
                    "duration_seconds": record.duration_seconds,
                    "result": record.result,
                    "error_message": record.error_message
                }
            }
        return {"success": False, "error": f"任务 {task_id} 不存在"}
    
    def _get_task(self, task_id: str) -> Dict[str, Any]:
        """获取任务详情"""
        if not task_id:
            return {"success": False, "error": "缺少 task_id"}
        
        task = self.scheduler.get_task(task_id)
        if task:
            return {
                "success": True,
                "task": task.model_dump()
            }
        return {"success": False, "error": f"任务 {task_id} 不存在"}
    
    def _list_tasks(self) -> Dict[str, Any]:
        """列出所有任务"""
        tasks = self.scheduler.list_tasks()
        return {
            "success": True,
            "count": len(tasks),
            "tasks": [
                {
                    "task_id": t.task_id,
                    "name": t.name,
                    "status": t.status.value,
                    "enabled": t.enabled,
                    "trigger_type": t.trigger.type.value,
                    "executor_type": t.executor.type.value
                }
                for t in tasks
            ]
        }
    
    def _get_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        if not task_id:
            return {"success": False, "error": "缺少 task_id"}
        
        status = self.scheduler.get_task_status(task_id)
        if status:
            # 转换 datetime 为字符串
            if status.get("last_run"):
                status["last_run"] = status["last_run"].isoformat()
            if status.get("next_run"):
                status["next_run"] = status["next_run"].isoformat()
            return {"success": True, "status": status}
        return {"success": False, "error": f"任务 {task_id} 不存在"}
    
    def _get_history(self, task_id: str, limit: int) -> Dict[str, Any]:
        """获取执行历史"""
        if not task_id:
            return {"success": False, "error": "缺少 task_id"}
        
        records = self.scheduler.get_execution_history(task_id, limit)
        return {
            "success": True,
            "count": len(records),
            "records": [
                {
                    "record_id": r.record_id,
                    "status": r.status.value,
                    "started_at": r.started_at.isoformat() if r.started_at else None,
                    "duration_seconds": r.duration_seconds,
                    "retry_count": r.retry_count,
                    "error_message": r.error_message
                }
                for r in records
            ]
        }
    
    def _get_examples(self) -> Dict[str, Any]:
        """获取示例配置"""
        return {
            "success": True,
            "examples": EXAMPLES
        }
    
    def _start_scheduler(self) -> Dict[str, Any]:
        """启动调度器"""
        self.scheduler.start()
        return {
            "success": True,
            "message": "调度器已启动"
        }
    
    def _stop_scheduler(self) -> Dict[str, Any]:
        """停止调度器"""
        self.scheduler.stop()
        return {
            "success": True,
            "message": "调度器已停止"
        }
    
    def _get_scheduler_stats(self) -> Dict[str, Any]:
        """获取调度器统计"""
        stats = self.scheduler.get_statistics()
        # 转换 datetime 为字符串
        if stats.get("started_at"):
            stats["started_at"] = stats["started_at"].isoformat() if stats["started_at"] else None
        return {
            "success": True,
            "stats": stats
        }


# 全局 API 实例
_api_instance: Optional[SchedulerAPI] = None


def get_scheduler_api() -> SchedulerAPI:
    """获取调度器 API 单例"""
    global _api_instance
    if _api_instance is None:
        _api_instance = SchedulerAPI()
    return _api_instance


def scheduler_action(action: str, **kwargs) -> Dict[str, Any]:
    """
    调度器操作快捷函数
    
    这是 AI 模型调用的主入口
    
    Args:
        action: 操作类型
            - create_task: 创建任务 (需要 task_config)
            - delete_task: 删除任务 (需要 task_id)
            - pause_task: 暂停任务 (需要 task_id)
            - resume_task: 恢复任务 (需要 task_id)
            - trigger_task: 手动触发 (需要 task_id)
            - get_task: 获取详情 (需要 task_id)
            - list_tasks: 列出所有任务
            - get_status: 获取状态 (需要 task_id)
            - get_history: 获取历史 (需要 task_id, 可选 limit)
            - get_examples: 获取示例配置
            - start_scheduler: 启动调度器
            - stop_scheduler: 停止调度器
            - get_scheduler_stats: 获取统计信息
        **kwargs: 操作参数
    
    Returns:
        操作结果字典
    
    Examples:
        # 创建每日任务
        scheduler_action("create_task", task_config={
            "name": "每日报告",
            "trigger": {"type": "daily", "time": "09:00:00"},
            "executor": {"type": "shell", "command": "python report.py"}
        })
        
        # 手动触发任务
        scheduler_action("trigger_task", task_id="daily_report")
        
        # 获取任务状态
        scheduler_action("get_status", task_id="daily_report")
    """
    api = get_scheduler_api()
    return api.execute(action, **kwargs)
