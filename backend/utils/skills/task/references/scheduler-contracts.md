# Scheduler Tool Contracts

任务调度器工具合约，用于创建和管理定时任务。

## Tool: `SchedulerAgent`

### 操作类型 (action)

| Action | 描述 | 必需参数 |
|--------|------|----------|
| `create_task` | 创建新任务 | `task_config` |
| `delete_task` | 删除任务 | `task_id` |
| `pause_task` | 暂停任务 | `task_id` |
| `resume_task` | 恢复任务 | `task_id` |
| `trigger_task` | 手动触发 | `task_id` |
| `get_task` | 获取详情 | `task_id` |
| `list_tasks` | 列出所有任务 | - |
| `get_status` | 获取状态 | `task_id` |
| `get_history` | 获取执行历史 | `task_id`, 可选 `limit` |
| `get_examples` | 获取示例配置 | - |
| `start_scheduler` | 启动调度器 | - |
| `stop_scheduler` | 停止调度器 | - |

### 触发类型 (trigger.type)

| Type | 描述 | 必需参数 |
|------|------|----------|
| `fixed_delay` | 固定延迟（任务完成后等待N秒） | `interval_seconds` |
| `fixed_rate` | 固定速率（每隔N秒触发） | `interval_seconds` |
| `daily` | 每日定时 | `time` (HH:MM:SS) |
| `weekly` | 每周定时 | `time`, `weekdays` ([1-7], 1=周一) |
| `monthly` | 每月定时 | `time`, `day` (1-31, -1=月末) |
| `yearly` | 每年定时 | `time`, `day`, `month` |
| `cron` | Cron表达式 | `cron_expr` |
| `once` | 一次性执行 | `run_at` (ISO datetime) |
| `delay` | 延迟执行 | `delay_seconds` |

### 执行器类型 (executor.type)

| Type | 描述 | 必需参数 |
|------|------|----------|
| `python_func` | Python函数 | `func_path` (module:func) |
| `shell` | Shell命令 | `command` |
| `http` | HTTP请求 | `url`, 可选 `method`, `headers`, `body` |
| `mcp_tool` | MCP工具 | `tool_name`, `tool_params` |

## 完整任务配置结构

```json
{
  "task_id": "string (可选，自动生成)",
  "name": "string (必填)",
  "description": "string (可选)",
  "tags": ["string"],
  
  "trigger": {
    "type": "string (必填)",
    "interval_seconds": "int",
    "time": "HH:MM:SS",
    "weekdays": [1, 2, 3, 4, 5],
    "day": "int 1-31 或 -1",
    "month": "int 1-12",
    "cron_expr": "string",
    "run_at": "ISO datetime",
    "delay_seconds": "int",
    "timezone": "Asia/Shanghai"
  },
  
  "executor": {
    "type": "string (必填)",
    "func_path": "module:func",
    "func_args": [],
    "func_kwargs": {},
    "command": "string",
    "working_dir": "string",
    "env": {},
    "url": "string",
    "method": "GET/POST/PUT/DELETE",
    "headers": {},
    "body": {},
    "tool_name": "string",
    "tool_params": {}
  },
  
  "priority": "int 1-10 (默认5)",
  "timeout_seconds": "int (默认3600)",
  "allow_concurrent": "bool (默认false)",
  
  "retry": {
    "max_retries": 3,
    "retry_interval_seconds": 300,
    "exponential_backoff": false,
    "backoff_multiplier": 2.0
  },
  
  "missed_policy": "ignore/fire_last/fire_all",
  "start_time": "ISO datetime",
  "end_time": "ISO datetime"
}
```
