"""
调度器数据模型
定义任务配置、触发规则、执行记录等核心数据结构
"""

from enum import Enum
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, field_validator
import uuid


class TriggerType(str, Enum):
    """触发类型"""
    # 间隔触发
    FIXED_DELAY = "fixed_delay"      # 固定延迟：任务完成后等待N时间再触发
    FIXED_RATE = "fixed_rate"        # 固定速率：每隔N时间强制触发
    
    # 周期触发
    DAILY = "daily"                  # 每日：指定时间
    WEEKLY = "weekly"                # 每周：指定星期+时间
    MONTHLY = "monthly"              # 每月：指定日期+时间
    YEARLY = "yearly"                # 每年：指定月日+时间
    CRON = "cron"                    # Cron表达式（高级）
    
    # 一次性触发
    ONCE = "once"                    # 指定时间点执行一次
    DELAY = "delay"                  # 延迟N时间执行一次


class ExecutorType(str, Enum):
    """执行器类型"""
    PYTHON_FUNC = "python_func"      # Python函数
    SHELL = "shell"                  # Shell脚本
    HTTP = "http"                    # HTTP请求
    MCP_TOOL = "mcp_tool"            # MCP工具调用


class TaskPriority(int, Enum):
    """任务优先级 (1-10, 数字越大优先级越高)"""
    LOWEST = 1
    LOW = 3
    NORMAL = 5
    HIGH = 7
    HIGHEST = 10


class MissedPolicy(str, Enum):
    """错过执行策略"""
    IGNORE = "ignore"                # 忽略
    FIRE_LAST = "fire_last"          # 仅补最后一次
    FIRE_ALL = "fire_all"            # 补所有错过的


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"              # 等待中
    RUNNING = "running"              # 执行中
    PAUSED = "paused"                # 已暂停
    COMPLETED = "completed"          # 已完成（一次性任务）
    FAILED = "failed"                # 失败
    CANCELLED = "cancelled"          # 已取消


class ExecutionStatus(str, Enum):
    """执行状态"""
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"              # 跳过（并发控制）
    RETRYING = "retrying"


class TriggerConfig(BaseModel):
    """触发配置"""
    type: TriggerType
    
    # 间隔触发参数
    interval_seconds: Optional[int] = None          # 间隔秒数
    
    # 周期触发参数
    time: Optional[str] = None                      # 时间 HH:MM:SS
    weekdays: Optional[List[int]] = None            # 星期几 (1-7, 1=周一)
    day: Optional[int] = None                       # 日期 (1-31, -1=月末)
    month: Optional[int] = None                     # 月份 (1-12)
    
    # Cron表达式
    cron_expr: Optional[str] = None                 # Cron表达式
    
    # 一次性触发参数
    run_at: Optional[datetime] = None               # 指定执行时间
    delay_seconds: Optional[int] = None             # 延迟秒数
    
    # 时区
    timezone: str = "Asia/Shanghai"
    
    @field_validator('weekdays', mode='before')
    @classmethod
    def validate_weekdays(cls, v):
        if v is None:
            return v
        if isinstance(v, list):
            for day in v:
                if not 1 <= day <= 7:
                    raise ValueError(f"星期必须在1-7之间，收到: {day}")
        return v
    
    @field_validator('day', mode='before')
    @classmethod
    def validate_day(cls, v):
        if v is None:
            return v
        if not (-1 <= v <= 31 and v != 0):
            raise ValueError(f"日期必须在1-31之间或-1(月末)，收到: {v}")
        return v


class RetryConfig(BaseModel):
    """重试配置"""
    max_retries: int = 3                            # 最大重试次数
    retry_interval_seconds: int = 300               # 重试间隔（秒）
    exponential_backoff: bool = False               # 是否指数退避
    backoff_multiplier: float = 2.0                 # 退避倍数


class NotifyConfig(BaseModel):
    """通知配置"""
    on_success: bool = False                        # 成功时通知
    on_failure: bool = True                         # 失败时通知
    on_timeout: bool = True                         # 超时时通知
    
    # 通知方式
    webhook_url: Optional[str] = None               # WebHook URL
    email: Optional[str] = None                     # 邮箱
    
    # 自定义通知处理器
    custom_handler: Optional[str] = None            # Python函数路径


class ExecutorConfig(BaseModel):
    """执行器配置"""
    type: ExecutorType
    
    # Python函数
    func_path: Optional[str] = None                 # 函数路径 module.path:func_name
    func_args: Optional[List[Any]] = None           # 位置参数
    func_kwargs: Optional[Dict[str, Any]] = None    # 关键字参数
    
    # Shell脚本
    command: Optional[str] = None                   # Shell命令
    working_dir: Optional[str] = None               # 工作目录
    env: Optional[Dict[str, str]] = None            # 环境变量
    
    # HTTP请求
    url: Optional[str] = None                       # 请求URL
    method: Optional[str] = "GET"                   # 请求方法
    headers: Optional[Dict[str, str]] = None        # 请求头
    body: Optional[Dict[str, Any]] = None           # 请求体
    
    # MCP工具
    tool_name: Optional[str] = None                 # 工具名称
    tool_params: Optional[Dict[str, Any]] = None    # 工具参数


class TaskConfig(BaseModel):
    """
    任务配置 - AI模型填写的核心结构
    
    示例:
    {
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
            "tool_name": "XHSSearchAgent",
            "tool_params": {
                "keywords": ["citywalk", "展览"],
                "city": "上海"
            }
        },
        "priority": 5,
        "timeout_seconds": 300,
        "allow_concurrent": false,
        "retry": {
            "max_retries": 3,
            "retry_interval_seconds": 60
        }
    }
    """
    # 基本信息
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    description: Optional[str] = None
    tags: Optional[List[str]] = None                # 标签，便于分类管理
    
    # 触发配置
    trigger: TriggerConfig
    
    # 执行器配置
    executor: ExecutorConfig
    
    # 任务控制
    priority: int = Field(default=TaskPriority.NORMAL, ge=1, le=10)
    timeout_seconds: Optional[int] = 3600           # 超时时间（秒），默认1小时
    allow_concurrent: bool = False                  # 是否允许并发执行
    
    # 重试配置
    retry: Optional[RetryConfig] = None
    
    # 通知配置
    notify: Optional[NotifyConfig] = None
    
    # 错过执行策略
    missed_policy: MissedPolicy = MissedPolicy.FIRE_LAST
    
    # 生效时间范围
    start_time: Optional[datetime] = None           # 开始生效时间
    end_time: Optional[datetime] = None             # 结束生效时间
    
    # 状态（运行时）
    status: TaskStatus = TaskStatus.PENDING
    enabled: bool = True
    
    # 元数据
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    def model_post_init(self, __context):
        """验证配置完整性"""
        self._validate_trigger()
        self._validate_executor()
    
    def _validate_trigger(self):
        """验证触发配置"""
        t = self.trigger
        if t.type in [TriggerType.FIXED_DELAY, TriggerType.FIXED_RATE]:
            if not t.interval_seconds:
                raise ValueError(f"{t.type} 需要设置 interval_seconds")
        
        elif t.type == TriggerType.DAILY:
            if not t.time:
                raise ValueError("DAILY 触发需要设置 time")
        
        elif t.type == TriggerType.WEEKLY:
            if not t.time or not t.weekdays:
                raise ValueError("WEEKLY 触发需要设置 time 和 weekdays")
        
        elif t.type == TriggerType.MONTHLY:
            if not t.time or not t.day:
                raise ValueError("MONTHLY 触发需要设置 time 和 day")
        
        elif t.type == TriggerType.YEARLY:
            if not t.time or not t.day or not t.month:
                raise ValueError("YEARLY 触发需要设置 time, day 和 month")
        
        elif t.type == TriggerType.CRON:
            if not t.cron_expr:
                raise ValueError("CRON 触发需要设置 cron_expr")
        
        elif t.type == TriggerType.ONCE:
            if not t.run_at:
                raise ValueError("ONCE 触发需要设置 run_at")
        
        elif t.type == TriggerType.DELAY:
            if not t.delay_seconds:
                raise ValueError("DELAY 触发需要设置 delay_seconds")
    
    def _validate_executor(self):
        """验证执行器配置"""
        e = self.executor
        if e.type == ExecutorType.PYTHON_FUNC:
            if not e.func_path:
                raise ValueError("PYTHON_FUNC 执行器需要设置 func_path")
        
        elif e.type == ExecutorType.SHELL:
            if not e.command:
                raise ValueError("SHELL 执行器需要设置 command")
        
        elif e.type == ExecutorType.HTTP:
            if not e.url:
                raise ValueError("HTTP 执行器需要设置 url")
        
        elif e.type == ExecutorType.MCP_TOOL:
            if not e.tool_name:
                raise ValueError("MCP_TOOL 执行器需要设置 tool_name")


class TaskExecutionRecord(BaseModel):
    """任务执行记录"""
    record_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    
    # 执行信息
    status: ExecutionStatus
    started_at: datetime
    finished_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    
    # 结果
    result: Optional[Any] = None
    error_message: Optional[str] = None
    error_traceback: Optional[str] = None
    
    # 重试信息
    retry_count: int = 0
    is_retry: bool = False
    
    # 触发信息
    scheduled_time: Optional[datetime] = None       # 计划执行时间
    actual_trigger: str = "scheduled"               # scheduled/manual/retry/missed


class SchedulerState(BaseModel):
    """调度器状态（持久化）"""
    tasks: Dict[str, TaskConfig] = {}
    last_run_times: Dict[str, datetime] = {}        # 任务最后执行时间
    next_run_times: Dict[str, datetime] = {}        # 任务下次执行时间
    execution_counts: Dict[str, int] = {}           # 执行次数统计
    
    # 调度器元数据
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    is_running: bool = False
