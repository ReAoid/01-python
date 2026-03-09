"""
通知模块
支持多种通知方式：WebHook、邮件、自定义处理器
"""

import importlib
import logging
from typing import Optional
import httpx

from backend.utils.scheduler.models import (
    NotifyConfig,
    TaskConfig,
    TaskExecutionRecord,
    ExecutionStatus
)

logger = logging.getLogger(__name__)


class Notifier:
    """通知器"""
    
    def notify(
        self,
        task: TaskConfig,
        record: TaskExecutionRecord,
        notify_config: Optional[NotifyConfig] = None
    ):
        """
        发送通知
        
        Args:
            task: 任务配置
            record: 执行记录
            notify_config: 通知配置（优先使用，否则使用任务配置中的）
        """
        config = notify_config or task.notify
        if not config:
            return
        
        # 判断是否需要通知
        should_notify = False
        if record.status == ExecutionStatus.SUCCESS and config.on_success:
            should_notify = True
        elif record.status == ExecutionStatus.FAILED and config.on_failure:
            should_notify = True
        elif record.status == ExecutionStatus.TIMEOUT and config.on_timeout:
            should_notify = True
        
        if not should_notify:
            return
        
        # 构建通知消息
        message = self._build_message(task, record)
        
        # 发送通知
        if config.webhook_url:
            self._send_webhook(config.webhook_url, task, record, message)
        
        if config.email:
            self._send_email(config.email, task, record, message)
        
        if config.custom_handler:
            self._call_custom_handler(config.custom_handler, task, record, message)
    
    def _build_message(self, task: TaskConfig, record: TaskExecutionRecord) -> dict:
        """构建通知消息"""
        status_emoji = {
            ExecutionStatus.SUCCESS: "✅",
            ExecutionStatus.FAILED: "❌",
            ExecutionStatus.TIMEOUT: "⏰",
        }
        
        return {
            "title": f"{status_emoji.get(record.status, '📋')} 任务执行通知",
            "task_id": task.task_id,
            "task_name": task.name,
            "status": record.status.value,
            "started_at": record.started_at.isoformat() if record.started_at else None,
            "finished_at": record.finished_at.isoformat() if record.finished_at else None,
            "duration_seconds": record.duration_seconds,
            "error_message": record.error_message,
            "retry_count": record.retry_count,
        }
    
    def _send_webhook(
        self, 
        url: str, 
        task: TaskConfig, 
        record: TaskExecutionRecord,
        message: dict
    ):
        """发送WebHook通知"""
        try:
            with httpx.Client(timeout=10) as client:
                response = client.post(url, json=message)
                response.raise_for_status()
                logger.info(f"WebHook通知发送成功: {task.task_id}")
        except Exception as e:
            logger.error(f"WebHook通知发送失败: {e}")
    
    def _send_email(
        self, 
        email: str, 
        task: TaskConfig, 
        record: TaskExecutionRecord,
        message: dict
    ):
        """发送邮件通知"""
        # 这里只是占位，实际需要配置SMTP
        logger.warning(f"邮件通知未实现，目标: {email}")
        # TODO: 实现邮件发送
        # import smtplib
        # from email.mime.text import MIMEText
    
    def _call_custom_handler(
        self, 
        handler_path: str, 
        task: TaskConfig, 
        record: TaskExecutionRecord,
        message: dict
    ):
        """调用自定义通知处理器"""
        try:
            # 解析处理器路径 module.path:func_name
            module_path, func_name = handler_path.rsplit(":", 1)
            module = importlib.import_module(module_path)
            handler = getattr(module, func_name)
            
            handler(task, record, message)
            logger.info(f"自定义通知处理器调用成功: {handler_path}")
        except Exception as e:
            logger.error(f"自定义通知处理器调用失败: {e}")
