"""
调度器参数结构定义
供 AI 模型填写和调用

这个文件定义了 AI 模型与调度器交互的标准接口
"""

from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field


# ==================== AI 调用接口 ====================

class SchedulerAction(BaseModel):
    """
    调度器操作 - AI 模型的统一调用接口
    
    支持的操作:
    - create_task: 创建新任务
    - delete_task: 删除任务
    - pause_task: 暂停任务
    - resume_task: 恢复任务
    - trigger_task: 手动触发任务
    - get_task: 获取任务详情
    - list_tasks: 列出所有任务
    - get_status: 获取任务状态
    - get_history: 获取执行历史
    """
    
    action: Literal[
        "create_task",
        "delete_task", 
        "pause_task",
        "resume_task",
        "trigger_task",
        "get_task",
        "list_tasks",
        "get_status",
        "get_history"
    ] = Field(..., description="要执行的操作")
    
    task_id: Optional[str] = Field(None, description="任务ID（除 create_task 和 list_tasks 外必填）")
    
    # create_task 专用参数
    task_config: Optional[Dict[str, Any]] = Field(None, description="任务配置（create_task 时必填）")
    
    # get_history 专用参数
    limit: Optional[int] = Field(100, description="返回记录数量限制")


# ==================== 任务配置模板 ====================

TASK_CONFIG_TEMPLATE = {
    "task_id": "string (可选，自动生成)",
    "name": "string (必填，任务名称)",
    "description": "string (可选，任务描述)",
    "tags": ["string (可选，标签列表)"],
    
    "trigger": {
        "type": "string (必填，触发类型)",
        # 触发类型选项:
        # - fixed_delay: 固定延迟（任务完成后等待N秒）
        # - fixed_rate: 固定速率（每隔N秒触发）
        # - daily: 每日（指定时间）
        # - weekly: 每周（指定星期+时间）
        # - monthly: 每月（指定日期+时间）
        # - yearly: 每年（指定月日+时间）
        # - cron: Cron表达式
        # - once: 一次性（指定时间点）
        # - delay: 延迟（从现在起延迟N秒）
        
        "interval_seconds": "int (fixed_delay/fixed_rate 必填)",
        "time": "string HH:MM:SS (daily/weekly/monthly/yearly 必填)",
        "weekdays": "[int] 1-7 (weekly 必填，1=周一)",
        "day": "int 1-31 或 -1=月末 (monthly/yearly 必填)",
        "month": "int 1-12 (yearly 必填)",
        "cron_expr": "string (cron 必填)",
        "run_at": "datetime ISO格式 (once 必填)",
        "delay_seconds": "int (delay 必填)",
        "timezone": "string (可选，默认 Asia/Shanghai)"
    },
    
    "executor": {
        "type": "string (必填，执行器类型)",
        # 执行器类型选项:
        # - python_func: Python函数
        # - shell: Shell命令
        # - http: HTTP请求
        # - mcp_tool: MCP工具
        
        # python_func 参数
        "func_path": "string module.path:func_name",
        "func_args": "[any] 位置参数",
        "func_kwargs": "{string: any} 关键字参数",
        
        # shell 参数
        "command": "string Shell命令",
        "working_dir": "string 工作目录",
        "env": "{string: string} 环境变量",
        
        # http 参数
        "url": "string 请求URL",
        "method": "string GET/POST/PUT/DELETE",
        "headers": "{string: string} 请求头",
        "body": "{string: any} 请求体",
        
        # mcp_tool 参数
        "tool_name": "string MCP工具名称",
        "tool_params": "{string: any} 工具参数"
    },
    
    "priority": "int 1-10 (可选，默认5，数字越大优先级越高)",
    "timeout_seconds": "int (可选，默认3600秒)",
    "allow_concurrent": "bool (可选，默认false)",
    
    "retry": {
        "max_retries": "int (可选，默认3)",
        "retry_interval_seconds": "int (可选，默认300秒)",
        "exponential_backoff": "bool (可选，默认false)",
        "backoff_multiplier": "float (可选，默认2.0)"
    },
    
    "notify": {
        "on_success": "bool (可选，默认false)",
        "on_failure": "bool (可选，默认true)",
        "on_timeout": "bool (可选，默认true)",
        "webhook_url": "string (可选)",
        "email": "string (可选)",
        "custom_handler": "string module.path:func_name (可选)"
    },
    
    "missed_policy": "string ignore/fire_last/fire_all (可选，默认fire_last)",
    "start_time": "datetime ISO格式 (可选，生效开始时间)",
    "end_time": "datetime ISO格式 (可选，生效结束时间)"
}


# ==================== 示例配置 ====================

EXAMPLES = {
    "每日定时任务": {
        "task_id": "daily_report",
        "name": "每日报告生成",
        "description": "每天早上9点生成日报",
        "trigger": {
            "type": "daily",
            "time": "09:00:00",
            "timezone": "Asia/Shanghai"
        },
        "executor": {
            "type": "python_func",
            "func_path": "backend.services.report:generate_daily_report"
        },
        "priority": 5
    },
    
    "每周定时任务": {
        "task_id": "weekly_xhs_search",
        "name": "每周小红书活动搜索",
        "description": "周一到周五搜索小红书活动信息",
        "trigger": {
            "type": "weekly",
            "weekdays": [1, 2, 3, 4, 5],
            "time": "09:00:00",
            "timezone": "Asia/Shanghai"
        },
        "executor": {
            "type": "mcp_tool",
            "tool_name": "SearchAgent",
            "tool_params": {
                "query": "上海 citywalk 周末活动 展览"
            }
        },
        "priority": 7,
        "retry": {
            "max_retries": 3,
            "retry_interval_seconds": 60
        }
    },
    
    "每月定时任务": {
        "task_id": "monthly_cleanup",
        "name": "每月数据清理",
        "description": "每月最后一天清理过期数据",
        "trigger": {
            "type": "monthly",
            "day": -1,
            "time": "23:00:00"
        },
        "executor": {
            "type": "shell",
            "command": "python scripts/cleanup.py --days 30"
        }
    },
    
    "固定间隔任务": {
        "task_id": "health_check",
        "name": "健康检查",
        "description": "每5分钟检查服务状态",
        "trigger": {
            "type": "fixed_rate",
            "interval_seconds": 300
        },
        "executor": {
            "type": "http",
            "url": "http://localhost:8000/health",
            "method": "GET"
        },
        "timeout_seconds": 30,
        "notify": {
            "on_failure": True,
            "webhook_url": "https://hooks.example.com/alert"
        }
    },
    
    "一次性任务": {
        "task_id": "scheduled_deploy",
        "name": "定时部署",
        "description": "在指定时间执行部署",
        "trigger": {
            "type": "once",
            "run_at": "2026-03-10T15:30:00"
        },
        "executor": {
            "type": "shell",
            "command": "bash deploy.sh"
        },
        "priority": 10
    },
    
    "延迟任务": {
        "task_id": "delayed_notification",
        "name": "延迟通知",
        "description": "1小时后发送提醒",
        "trigger": {
            "type": "delay",
            "delay_seconds": 3600
        },
        "executor": {
            "type": "http",
            "url": "https://api.example.com/notify",
            "method": "POST",
            "body": {"message": "提醒：任务即将开始"}
        }
    },
    
    "周六汇总任务": {
        "task_id": "weekly_summary",
        "name": "周六活动汇总",
        "description": "每周六上午10点汇总本周搜索结果",
        "trigger": {
            "type": "weekly",
            "weekdays": [6],
            "time": "10:00:00"
        },
        "executor": {
            "type": "python_func",
            "func_path": "backend.services.aggregator:generate_weekly_summary",
            "func_kwargs": {
                "source_task": "weekly_xhs_search",
                "output_format": "markdown"
            }
        },
        "priority": 8
    }
}


def get_task_config_schema() -> dict:
    """获取任务配置的JSON Schema"""
    from backend.utils.scheduler.models import TaskConfig
    return TaskConfig.model_json_schema()


def validate_task_config(config: dict) -> tuple[bool, str]:
    """
    验证任务配置
    
    Returns:
        (是否有效, 错误信息)
    """
    try:
        from backend.utils.scheduler.models import TaskConfig
        TaskConfig(**config)
        return True, ""
    except Exception as e:
        return False, str(e)
