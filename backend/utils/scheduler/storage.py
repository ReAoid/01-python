"""
持久化存储模块
支持任务配置和执行记录的持久化
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from filelock import FileLock
import logging

from backend.utils.scheduler.models import (
    TaskConfig,
    TaskExecutionRecord,
    SchedulerState
)

logger = logging.getLogger(__name__)


class DateTimeEncoder(json.JSONEncoder):
    """支持datetime的JSON编码器"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def datetime_decoder(dct):
    """JSON解码时转换datetime字符串"""
    for key, value in dct.items():
        if isinstance(value, str):
            # 尝试解析ISO格式的datetime
            try:
                if 'T' in value and len(value) >= 19:
                    dct[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
            except (ValueError, TypeError):
                pass
    return dct


class SchedulerStorage:
    """调度器存储"""
    
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = os.path.join(
                os.path.dirname(__file__),
                "..", "..", "data", "scheduler"
            )
        
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 文件路径
        self.state_file = self.data_dir / "scheduler_state.json"
        self.tasks_dir = self.data_dir / "tasks"
        self.records_dir = self.data_dir / "records"
        
        self.tasks_dir.mkdir(exist_ok=True)
        self.records_dir.mkdir(exist_ok=True)
        
        # 文件锁
        self.state_lock = FileLock(str(self.state_file) + ".lock")
    
    # ==================== 状态管理 ====================
    
    def load_state(self) -> SchedulerState:
        """加载调度器状态"""
        with self.state_lock:
            if not self.state_file.exists():
                return SchedulerState()
            
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f, object_hook=datetime_decoder)
                
                # 重建任务配置
                tasks = {}
                for task_id, task_data in data.get('tasks', {}).items():
                    try:
                        tasks[task_id] = TaskConfig(**task_data)
                    except Exception as e:
                        logger.error(f"加载任务 {task_id} 失败: {e}")
                
                data['tasks'] = tasks
                return SchedulerState(**data)
                
            except Exception as e:
                logger.error(f"加载调度器状态失败: {e}")
                return SchedulerState()
    
    def save_state(self, state: SchedulerState):
        """保存调度器状态"""
        with self.state_lock:
            # 转换任务为可序列化格式
            data = state.model_dump()
            data['tasks'] = {
                task_id: task.model_dump() 
                for task_id, task in state.tasks.items()
            }
            
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, cls=DateTimeEncoder, ensure_ascii=False, indent=2)
    
    # ==================== 任务管理 ====================
    
    def save_task(self, task: TaskConfig):
        """保存单个任务配置"""
        task_file = self.tasks_dir / f"{task.task_id}.json"
        with open(task_file, 'w', encoding='utf-8') as f:
            json.dump(task.model_dump(), f, cls=DateTimeEncoder, ensure_ascii=False, indent=2)
    
    def load_task(self, task_id: str) -> Optional[TaskConfig]:
        """加载单个任务配置"""
        task_file = self.tasks_dir / f"{task_id}.json"
        if not task_file.exists():
            return None
        
        try:
            with open(task_file, 'r', encoding='utf-8') as f:
                data = json.load(f, object_hook=datetime_decoder)
            return TaskConfig(**data)
        except Exception as e:
            logger.error(f"加载任务 {task_id} 失败: {e}")
            return None
    
    def delete_task(self, task_id: str) -> bool:
        """删除任务配置"""
        task_file = self.tasks_dir / f"{task_id}.json"
        if task_file.exists():
            task_file.unlink()
            return True
        return False
    
    def list_tasks(self) -> List[str]:
        """列出所有任务ID"""
        return [f.stem for f in self.tasks_dir.glob("*.json")]
    
    # ==================== 执行记录 ====================
    
    def save_record(self, record: TaskExecutionRecord):
        """保存执行记录"""
        # 按任务ID和日期组织
        date_str = record.started_at.strftime("%Y-%m-%d")
        record_dir = self.records_dir / record.task_id / date_str
        record_dir.mkdir(parents=True, exist_ok=True)
        
        record_file = record_dir / f"{record.record_id}.json"
        with open(record_file, 'w', encoding='utf-8') as f:
            json.dump(record.model_dump(), f, cls=DateTimeEncoder, ensure_ascii=False, indent=2)
    
    def get_records(
        self, 
        task_id: str, 
        date: Optional[str] = None,
        limit: int = 100
    ) -> List[TaskExecutionRecord]:
        """获取执行记录"""
        records = []
        task_records_dir = self.records_dir / task_id
        
        if not task_records_dir.exists():
            return records
        
        # 获取日期目录
        if date:
            date_dirs = [task_records_dir / date]
        else:
            date_dirs = sorted(task_records_dir.iterdir(), reverse=True)
        
        for date_dir in date_dirs:
            if not date_dir.is_dir():
                continue
            
            for record_file in sorted(date_dir.glob("*.json"), reverse=True):
                if len(records) >= limit:
                    break
                
                try:
                    with open(record_file, 'r', encoding='utf-8') as f:
                        data = json.load(f, object_hook=datetime_decoder)
                    records.append(TaskExecutionRecord(**data))
                except Exception as e:
                    logger.error(f"加载记录 {record_file} 失败: {e}")
            
            if len(records) >= limit:
                break
        
        return records
    
    def get_latest_record(self, task_id: str) -> Optional[TaskExecutionRecord]:
        """获取最新的执行记录"""
        records = self.get_records(task_id, limit=1)
        return records[0] if records else None
    
    def cleanup_old_records(self, days: int = 30):
        """清理旧的执行记录"""
        cutoff = datetime.now().date()
        from datetime import timedelta
        cutoff = cutoff - timedelta(days=days)
        
        for task_dir in self.records_dir.iterdir():
            if not task_dir.is_dir():
                continue
            
            for date_dir in task_dir.iterdir():
                if not date_dir.is_dir():
                    continue
                
                try:
                    dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d").date()
                    if dir_date < cutoff:
                        # 删除整个日期目录
                        import shutil
                        shutil.rmtree(date_dir)
                        logger.info(f"清理旧记录: {date_dir}")
                except ValueError:
                    pass
