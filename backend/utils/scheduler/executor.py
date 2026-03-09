"""
执行器模块
支持多种任务执行方式：Python函数、Shell脚本、HTTP请求、MCP工具
"""

import asyncio
import importlib
import subprocess
import traceback
from datetime import datetime
from typing import Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import logging
import httpx

from backend.utils.scheduler.models import (
    ExecutorConfig, 
    ExecutorType, 
    TaskExecutionRecord,
    ExecutionStatus
)

logger = logging.getLogger(__name__)


class TaskExecutor:
    """任务执行器"""
    
    def __init__(self, max_workers: int = 10):
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        self._mcp_manager = None
    
    @property
    def mcp_manager(self):
        """延迟加载 MCP Manager"""
        if self._mcp_manager is None:
            from backend.utils.mcp.manager import get_mcp_manager
            self._mcp_manager = get_mcp_manager(auto_setup_logger=False)
        return self._mcp_manager
    
    def execute(
        self,
        task_id: str,
        executor_config: ExecutorConfig,
        timeout_seconds: Optional[int] = None,
        scheduled_time: Optional[datetime] = None,
        retry_count: int = 0,
        is_retry: bool = False
    ) -> TaskExecutionRecord:
        """
        执行任务
        
        Args:
            task_id: 任务ID
            executor_config: 执行器配置
            timeout_seconds: 超时时间
            scheduled_time: 计划执行时间
            retry_count: 重试次数
            is_retry: 是否为重试
        
        Returns:
            执行记录
        """
        started_at = datetime.now()
        record = TaskExecutionRecord(
            task_id=task_id,
            status=ExecutionStatus.SUCCESS,
            started_at=started_at,
            scheduled_time=scheduled_time,
            retry_count=retry_count,
            is_retry=is_retry,
            actual_trigger="retry" if is_retry else "scheduled"
        )
        
        try:
            # 根据执行器类型选择执行方法
            if executor_config.type == ExecutorType.PYTHON_FUNC:
                result = self._execute_python_func(executor_config, timeout_seconds)
            
            elif executor_config.type == ExecutorType.SHELL:
                result = self._execute_shell(executor_config, timeout_seconds)
            
            elif executor_config.type == ExecutorType.HTTP:
                result = self._execute_http(executor_config, timeout_seconds)
            
            elif executor_config.type == ExecutorType.MCP_TOOL:
                result = self._execute_mcp_tool(executor_config, timeout_seconds)
            
            else:
                raise ValueError(f"不支持的执行器类型: {executor_config.type}")
            
            record.result = result
            record.status = ExecutionStatus.SUCCESS
            
        except FuturesTimeoutError:
            record.status = ExecutionStatus.TIMEOUT
            record.error_message = f"任务执行超时 ({timeout_seconds}秒)"
            logger.error(f"任务 {task_id} 执行超时")
        
        except Exception as e:
            record.status = ExecutionStatus.FAILED
            record.error_message = str(e)
            record.error_traceback = traceback.format_exc()
            logger.exception(f"任务 {task_id} 执行失败")
        
        finally:
            record.finished_at = datetime.now()
            record.duration_seconds = (record.finished_at - started_at).total_seconds()
        
        return record
    
    def _execute_python_func(
        self, 
        config: ExecutorConfig, 
        timeout: Optional[int]
    ) -> Any:
        """执行Python函数"""
        # 解析函数路径 module.path:func_name
        module_path, func_name = config.func_path.rsplit(":", 1)
        module = importlib.import_module(module_path)
        func: Callable = getattr(module, func_name)
        
        args = config.func_args or []
        kwargs = config.func_kwargs or {}
        
        # 检查是否为异步函数
        if asyncio.iscoroutinefunction(func):
            future = self.thread_pool.submit(
                lambda: asyncio.run(func(*args, **kwargs))
            )
        else:
            future = self.thread_pool.submit(func, *args, **kwargs)
        
        return future.result(timeout=timeout)
    
    def _execute_shell(
        self, 
        config: ExecutorConfig, 
        timeout: Optional[int]
    ) -> str:
        """执行Shell命令"""
        result = subprocess.run(
            config.command,
            shell=True,
            cwd=config.working_dir,
            env=config.env,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.returncode != 0:
            raise RuntimeError(
                f"Shell命令执行失败 (exit code: {result.returncode})\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )
        
        return result.stdout
    
    def _execute_http(
        self, 
        config: ExecutorConfig, 
        timeout: Optional[int]
    ) -> dict:
        """执行HTTP请求"""
        with httpx.Client(timeout=timeout) as client:
            response = client.request(
                method=config.method or "GET",
                url=config.url,
                headers=config.headers,
                json=config.body if config.method in ["POST", "PUT", "PATCH"] else None,
                params=config.body if config.method == "GET" else None
            )
            response.raise_for_status()
            
            try:
                return response.json()
            except:
                return {"text": response.text, "status_code": response.status_code}
    
    def _execute_mcp_tool(
        self, 
        config: ExecutorConfig, 
        timeout: Optional[int]
    ) -> str:
        """执行MCP工具"""
        def run_tool():
            return self.mcp_manager.call_tool(
                config.tool_name,
                config.tool_params or {}
            )
        
        future = self.thread_pool.submit(run_tool)
        return future.result(timeout=timeout)
    
    def shutdown(self):
        """关闭执行器"""
        self.thread_pool.shutdown(wait=True)
