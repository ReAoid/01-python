"""
调度器核心模块
统一管理任务的注册、调度、执行
"""

import threading
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable
from queue import PriorityQueue
from dataclasses import dataclass, field
import logging
from zoneinfo import ZoneInfo

from backend.utils.scheduler.models import (
    TaskConfig,
    TaskStatus,
    TaskExecutionRecord,
    ExecutionStatus,
    MissedPolicy,
    TriggerType,
    SchedulerState
)
from backend.utils.scheduler.trigger import TriggerCalculator, get_missed_runs
from backend.utils.scheduler.executor import TaskExecutor
from backend.utils.scheduler.storage import SchedulerStorage
from backend.utils.scheduler.notifier import Notifier

logger = logging.getLogger(__name__)


@dataclass(order=True)
class ScheduledTask:
    """调度队列中的任务项"""
    priority: int  # 负数，因为PriorityQueue是最小堆
    next_run: datetime = field(compare=False)
    task_id: str = field(compare=False)


class Scheduler:
    """
    任务调度器
    
    功能：
    - 多种触发方式（间隔、周期、一次性、延迟）
    - 任务生命周期管理（注册、注销、暂停、恢复、手动触发）
    - 优先级控制
    - 并发控制
    - 超时控制
    - 重试机制
    - 状态持久化
    - 错过执行处理
    - 通知机制
    """
    
    def __init__(
        self,
        storage: Optional[SchedulerStorage] = None,
        executor: Optional[TaskExecutor] = None,
        notifier: Optional[Notifier] = None,
        check_interval: float = 1.0
    ):
        self.storage = storage or SchedulerStorage()
        self.executor = executor or TaskExecutor()
        self.notifier = notifier or Notifier()
        self.check_interval = check_interval
        
        # 状态
        self.state = SchedulerState()
        self.task_queue: PriorityQueue[ScheduledTask] = PriorityQueue()
        
        # 运行中的任务（用于并发控制）
        self.running_tasks: Dict[str, threading.Thread] = {}
        self.running_lock = threading.Lock()
        
        # 调度线程
        self._scheduler_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # 加载持久化状态
        self._load_state()
    
    def _load_state(self):
        """加载持久化状态"""
        self.state = self.storage.load_state()
        
        # 重建任务队列
        for task_id, task in self.state.tasks.items():
            if task.enabled and task.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]:
                self._schedule_task(task)
        
        logger.info(f"加载了 {len(self.state.tasks)} 个任务")
    
    def _save_state(self):
        """保存状态"""
        self.storage.save_state(self.state)
    
    # ==================== 任务管理 ====================
    
    def register_task(self, task: TaskConfig) -> str:
        """
        注册任务
        
        Args:
            task: 任务配置
        
        Returns:
            任务ID
        """
        task_id = task.task_id
        
        # 检查是否已存在
        if task_id in self.state.tasks:
            raise ValueError(f"任务 {task_id} 已存在")
        
        # 保存任务
        self.state.tasks[task_id] = task
        self.storage.save_task(task)
        
        # 调度任务
        if task.enabled:
            self._schedule_task(task)
        
        self._save_state()
        logger.info(f"注册任务: {task_id} ({task.name})")
        
        return task_id
    
    def unregister_task(self, task_id: str) -> bool:
        """注销任务"""
        if task_id not in self.state.tasks:
            return False
        
        # 从状态中移除
        del self.state.tasks[task_id]
        self.state.last_run_times.pop(task_id, None)
        self.state.next_run_times.pop(task_id, None)
        self.state.execution_counts.pop(task_id, None)
        
        # 删除持久化文件
        self.storage.delete_task(task_id)
        
        self._save_state()
        logger.info(f"注销任务: {task_id}")
        
        return True
    
    def pause_task(self, task_id: str) -> bool:
        """暂停任务"""
        if task_id not in self.state.tasks:
            return False
        
        task = self.state.tasks[task_id]
        task.status = TaskStatus.PAUSED
        task.enabled = False
        task.updated_at = datetime.now()
        
        self.storage.save_task(task)
        self._save_state()
        logger.info(f"暂停任务: {task_id}")
        
        return True
    
    def resume_task(self, task_id: str) -> bool:
        """恢复任务"""
        if task_id not in self.state.tasks:
            return False
        
        task = self.state.tasks[task_id]
        task.status = TaskStatus.PENDING
        task.enabled = True
        task.updated_at = datetime.now()
        
        # 重新调度
        self._schedule_task(task)
        
        self.storage.save_task(task)
        self._save_state()
        logger.info(f"恢复任务: {task_id}")
        
        return True
    
    def trigger_task(self, task_id: str) -> Optional[TaskExecutionRecord]:
        """
        手动触发任务
        
        Args:
            task_id: 任务ID
        
        Returns:
            执行记录
        """
        if task_id not in self.state.tasks:
            logger.error(f"任务不存在: {task_id}")
            return None
        
        task = self.state.tasks[task_id]
        logger.info(f"手动触发任务: {task_id}")
        
        record = self._execute_task(task, manual=True)
        return record
    
    def get_task(self, task_id: str) -> Optional[TaskConfig]:
        """获取任务配置"""
        return self.state.tasks.get(task_id)
    
    def list_tasks(self) -> List[TaskConfig]:
        """列出所有任务"""
        return list(self.state.tasks.values())
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        if task_id not in self.state.tasks:
            return None
        
        task = self.state.tasks[task_id]
        return {
            "task_id": task_id,
            "name": task.name,
            "status": task.status.value,
            "enabled": task.enabled,
            "last_run": self.state.last_run_times.get(task_id),
            "next_run": self.state.next_run_times.get(task_id),
            "execution_count": self.state.execution_counts.get(task_id, 0),
            "is_running": task_id in self.running_tasks
        }

    # ==================== 调度逻辑 ====================
    
    def _schedule_task(self, task: TaskConfig):
        """将任务加入调度队列"""
        last_run = self.state.last_run_times.get(task.task_id)
        
        # 计算下次执行时间
        next_run = TriggerCalculator.get_next_run_time(
            task.trigger,
            last_run_time=last_run
        )
        
        if next_run is None:
            # 一次性任务已完成
            task.status = TaskStatus.COMPLETED
            return
        
        # 检查生效时间范围
        now = datetime.now(ZoneInfo(task.trigger.timezone))
        if task.start_time and next_run < task.start_time:
            next_run = task.start_time
        if task.end_time and next_run > task.end_time:
            task.status = TaskStatus.COMPLETED
            return
        
        # 记录下次执行时间
        self.state.next_run_times[task.task_id] = next_run
        
        # 加入优先级队列（负数优先级，因为是最小堆）
        scheduled = ScheduledTask(
            priority=-task.priority,
            next_run=next_run,
            task_id=task.task_id
        )
        self.task_queue.put(scheduled)
    
    def _check_and_execute(self):
        """检查并执行到期任务"""
        now = datetime.now()
        tasks_to_reschedule = []
        
        while not self.task_queue.empty():
            # 查看队首任务
            try:
                scheduled = self.task_queue.get_nowait()
            except:
                break
            
            task_id = scheduled.task_id
            
            # 检查任务是否还存在且启用
            if task_id not in self.state.tasks:
                continue
            
            task = self.state.tasks[task_id]
            if not task.enabled or task.status == TaskStatus.PAUSED:
                continue
            
            # 处理时区
            next_run = scheduled.next_run
            if next_run.tzinfo:
                now_tz = datetime.now(next_run.tzinfo)
            else:
                now_tz = now
            
            # 检查是否到执行时间
            if next_run > now_tz:
                # 还没到时间，放回队列
                self.task_queue.put(scheduled)
                break
            
            # 执行任务（在新线程中）
            self._execute_task_async(task)
            
            # 重新调度（非一次性任务）
            if task.trigger.type not in [TriggerType.ONCE, TriggerType.DELAY]:
                tasks_to_reschedule.append(task)
        
        # 重新调度任务
        for task in tasks_to_reschedule:
            self._schedule_task(task)
    
    def _execute_task_async(self, task: TaskConfig):
        """异步执行任务"""
        task_id = task.task_id
        
        # 并发控制
        with self.running_lock:
            if task_id in self.running_tasks and not task.allow_concurrent:
                logger.warning(f"任务 {task_id} 正在执行中，跳过本次触发")
                # 记录跳过
                record = TaskExecutionRecord(
                    task_id=task_id,
                    status=ExecutionStatus.SKIPPED,
                    started_at=datetime.now(),
                    finished_at=datetime.now(),
                    duration_seconds=0
                )
                self.storage.save_record(record)
                return
            
            # 创建执行线程
            thread = threading.Thread(
                target=self._execute_task,
                args=(task,),
                name=f"task-{task_id}"
            )
            self.running_tasks[task_id] = thread
        
        thread.start()
    
    def _execute_task(
        self, 
        task: TaskConfig, 
        manual: bool = False,
        retry_count: int = 0
    ) -> TaskExecutionRecord:
        """执行任务"""
        task_id = task.task_id
        
        try:
            # 更新状态
            task.status = TaskStatus.RUNNING
            
            # 执行
            record = self.executor.execute(
                task_id=task_id,
                executor_config=task.executor,
                timeout_seconds=task.timeout_seconds,
                scheduled_time=self.state.next_run_times.get(task_id),
                retry_count=retry_count,
                is_retry=retry_count > 0
            )
            
            if manual:
                record.actual_trigger = "manual"
            
            # 保存记录
            self.storage.save_record(record)
            
            # 更新统计
            self.state.last_run_times[task_id] = record.started_at
            self.state.execution_counts[task_id] = \
                self.state.execution_counts.get(task_id, 0) + 1
            
            # 处理失败重试
            if record.status == ExecutionStatus.FAILED and task.retry:
                if retry_count < task.retry.max_retries:
                    self._schedule_retry(task, retry_count + 1)
            
            # 发送通知
            self.notifier.notify(task, record)
            
            # 更新任务状态
            if record.status == ExecutionStatus.SUCCESS:
                task.status = TaskStatus.PENDING
            elif record.status == ExecutionStatus.FAILED:
                if not task.retry or retry_count >= task.retry.max_retries:
                    task.status = TaskStatus.FAILED
            
            self._save_state()
            
            return record
            
        finally:
            # 从运行中移除
            with self.running_lock:
                self.running_tasks.pop(task_id, None)
    
    def _schedule_retry(self, task: TaskConfig, retry_count: int):
        """调度重试"""
        retry_config = task.retry
        
        # 计算重试间隔
        interval = retry_config.retry_interval_seconds
        if retry_config.exponential_backoff:
            interval = interval * (retry_config.backoff_multiplier ** (retry_count - 1))
        
        # 延迟执行重试
        def do_retry():
            time.sleep(interval)
            self._execute_task(task, retry_count=retry_count)
        
        thread = threading.Thread(target=do_retry, name=f"retry-{task.task_id}")
        thread.start()
        
        logger.info(f"任务 {task.task_id} 将在 {interval} 秒后重试 (第{retry_count}次)")
    
    # ==================== 错过执行处理 ====================
    
    def _handle_missed_executions(self):
        """处理错过的执行"""
        now = datetime.now()
        
        for task_id, task in self.state.tasks.items():
            if not task.enabled or task.status == TaskStatus.PAUSED:
                continue
            
            last_run = self.state.last_run_times.get(task_id)
            if not last_run:
                continue
            
            # 获取错过的执行
            missed = get_missed_runs(task.trigger, last_run, now)
            
            if not missed:
                continue
            
            logger.info(f"任务 {task_id} 错过了 {len(missed)} 次执行")
            
            # 根据策略处理
            if task.missed_policy == MissedPolicy.IGNORE:
                pass
            
            elif task.missed_policy == MissedPolicy.FIRE_LAST:
                # 只补最后一次
                self._execute_task_async(task)
            
            elif task.missed_policy == MissedPolicy.FIRE_ALL:
                # 补所有（限制数量避免雪崩）
                for i, missed_time in enumerate(missed[-10:]):  # 最多补10次
                    self._execute_task_async(task)
                    time.sleep(1)  # 间隔执行

    # ==================== 调度器控制 ====================
    
    def start(self, daemon: bool = True):
        """
        启动调度器
        
        Args:
            daemon: 是否作为守护线程运行
        """
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            logger.warning("调度器已在运行")
            return
        
        self._stop_event.clear()
        self.state.is_running = True
        self.state.started_at = datetime.now()
        
        # 处理错过的执行
        self._handle_missed_executions()
        
        # 启动调度线程
        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            name="scheduler-main",
            daemon=daemon
        )
        self._scheduler_thread.start()
        
        self._save_state()
        logger.info("调度器已启动")
    
    def stop(self, wait: bool = True, timeout: float = 30):
        """
        停止调度器
        
        Args:
            wait: 是否等待当前任务完成
            timeout: 等待超时时间
        """
        self._stop_event.set()
        self.state.is_running = False
        self.state.stopped_at = datetime.now()
        
        if wait and self._scheduler_thread:
            self._scheduler_thread.join(timeout=timeout)
        
        # 等待运行中的任务
        if wait:
            with self.running_lock:
                for task_id, thread in list(self.running_tasks.items()):
                    thread.join(timeout=timeout)
        
        self._save_state()
        logger.info("调度器已停止")
    
    def _scheduler_loop(self):
        """调度主循环"""
        while not self._stop_event.is_set():
            try:
                self._check_and_execute()
            except Exception as e:
                logger.exception("调度循环异常")
            
            # 等待下一次检查
            self._stop_event.wait(self.check_interval)
    
    def is_running(self) -> bool:
        """检查调度器是否运行中"""
        return self.state.is_running and self._scheduler_thread and self._scheduler_thread.is_alive()
    
    # ==================== 统计与查询 ====================
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取调度器统计信息"""
        return {
            "is_running": self.is_running(),
            "started_at": self.state.started_at,
            "total_tasks": len(self.state.tasks),
            "enabled_tasks": sum(1 for t in self.state.tasks.values() if t.enabled),
            "running_tasks": len(self.running_tasks),
            "pending_in_queue": self.task_queue.qsize(),
            "execution_counts": self.state.execution_counts.copy()
        }
    
    def get_execution_history(
        self, 
        task_id: str, 
        limit: int = 100
    ) -> List[TaskExecutionRecord]:
        """获取任务执行历史"""
        return self.storage.get_records(task_id, limit=limit)


# ==================== 全局单例 ====================

_scheduler_instance: Optional[Scheduler] = None


def get_scheduler() -> Scheduler:
    """获取全局调度器单例"""
    global _scheduler_instance
    
    if _scheduler_instance is None:
        _scheduler_instance = Scheduler()
    
    return _scheduler_instance


def reset_scheduler():
    """重置调度器单例（主要用于测试）"""
    global _scheduler_instance
    if _scheduler_instance:
        _scheduler_instance.stop(wait=False)
    _scheduler_instance = None
