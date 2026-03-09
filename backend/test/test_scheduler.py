"""
调度器模块测试文件

测试调度器各项功能（清晰分阶段测试）:

阶段 1: 触发器配置测试 (TriggerConfig)
阶段 2: 任务配置测试 (TaskConfig)
阶段 3: 调度器基本功能测试 (Scheduler)
阶段 4: 任务执行测试
阶段 5: API 接口测试 (SchedulerAPI)

使用方法：
    cd /Users/mingy/Documents/python/01-python
    python backend/test/test_scheduler.py
"""

import asyncio
import sys
import logging
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from backend.config import paths

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# 路径配置
# -----------------------------------------------------------------------------
ROOT_DIR = paths.get_root_dir()

# 确保 backend 模块可以被导入
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

try:
    from backend.utils.scheduler import (
        TaskConfig,
        TriggerConfig,
        TriggerType,
        ExecutorType,
        ExecutorConfig,
        TaskPriority,
        MissedPolicy,
        TaskStatus,
        Scheduler,
        get_scheduler,
    )
    from backend.utils.scheduler.api import SchedulerAPI, scheduler_action
    from backend.utils.scheduler.storage import SchedulerStorage
except ImportError as e:
    print(f"❌ 无法导入必要模块: {e}")
    print("请检查项目路径配置")
    sys.exit(1)


class SchedulerTester:
    """调度器测试类 - 分阶段测试调度器功能"""
    
    def __init__(self):
        self.temp_dir = None
        self.scheduler = None
        self.test_results = []
    
    def setup(self):
        """测试前准备"""
        # 创建临时测试目录（在项目内）
        test_dir = Path(__file__).parent / "scheduler_test_data"
        test_dir.mkdir(exist_ok=True)
        self.temp_dir = str(test_dir)
        logger.info(f"创建临时测试目录: {self.temp_dir}")
        
        # 创建调度器实例（使用临时存储）
        storage = SchedulerStorage(data_dir=self.temp_dir)
        self.scheduler = Scheduler(storage=storage)
    
    def cleanup(self):
        """测试后清理"""
        # 停止调度器
        if self.scheduler and self.scheduler.is_running():
            self.scheduler.stop(wait=False)
        
        # 清理临时目录内容（保留目录本身便于调试）
        if self.temp_dir and Path(self.temp_dir).exists():
            for item in Path(self.temp_dir).iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            logger.info(f"清理临时测试目录内容: {self.temp_dir}")
    
    def test_trigger_config(self) -> bool:
        """
        阶段 1: 触发器配置测试
        
        测试内容：
        - 间隔触发配置
        - 周期触发配置
        - 一次性触发配置
        - 配置验证
        """
        print("\n" + "="*60)
        print("阶段 1: 触发器配置测试 (TriggerConfig)")
        print("="*60)
        
        try:
            # 测试 1.1: 固定间隔触发
            print("\n[1.1] 创建固定间隔触发配置...")
            trigger_interval = TriggerConfig(
                type=TriggerType.FIXED_RATE,
                interval_seconds=60
            )
            assert trigger_interval.type == TriggerType.FIXED_RATE
            assert trigger_interval.interval_seconds == 60
            print(f"✅ 固定间隔触发配置创建成功: 每 {trigger_interval.interval_seconds} 秒")
            
            # 测试 1.2: 每日触发
            print("\n[1.2] 创建每日触发配置...")
            trigger_daily = TriggerConfig(
                type=TriggerType.DAILY,
                time="09:00:00"
            )
            assert trigger_daily.type == TriggerType.DAILY
            assert trigger_daily.time == "09:00:00"
            print(f"✅ 每日触发配置创建成功: 每天 {trigger_daily.time}")
            
            # 测试 1.3: 每周触发
            print("\n[1.3] 创建每周触发配置...")
            trigger_weekly = TriggerConfig(
                type=TriggerType.WEEKLY,
                weekdays=[1, 2, 3, 4, 5],  # 周一到周五
                time="09:00:00"
            )
            assert trigger_weekly.type == TriggerType.WEEKLY
            assert len(trigger_weekly.weekdays) == 5
            print(f"✅ 每周触发配置创建成功: 周一至周五 {trigger_weekly.time}")
            
            # 测试 1.4: 一次性触发
            print("\n[1.4] 创建一次性触发配置...")
            run_time = datetime.now() + timedelta(hours=1)
            trigger_once = TriggerConfig(
                type=TriggerType.ONCE,
                run_at=run_time
            )
            assert trigger_once.type == TriggerType.ONCE
            assert trigger_once.run_at == run_time
            print(f"✅ 一次性触发配置创建成功: {trigger_once.run_at}")
            
            # 测试 1.5: 延迟触发
            print("\n[1.5] 创建延迟触发配置...")
            trigger_delay = TriggerConfig(
                type=TriggerType.DELAY,
                delay_seconds=300
            )
            assert trigger_delay.type == TriggerType.DELAY
            assert trigger_delay.delay_seconds == 300
            print(f"✅ 延迟触发配置创建成功: 延迟 {trigger_delay.delay_seconds} 秒")
            
            print("\n✅ 阶段 1 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 1 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_task_config(self) -> bool:
        """
        阶段 2: 任务配置测试
        
        测试内容：
        - 创建任务配置
        - 不同执行器类型
        - 任务优先级
        - 重试配置
        """
        print("\n" + "="*60)
        print("阶段 2: 任务配置测试 (TaskConfig)")
        print("="*60)
        
        try:
            # 测试 2.1: Shell 执行器任务
            print("\n[2.1] 创建 Shell 执行器任务...")
            task_shell = TaskConfig(
                name="测试Shell任务",
                description="执行简单的Shell命令",
                trigger=TriggerConfig(
                    type=TriggerType.FIXED_RATE,
                    interval_seconds=60
                ),
                executor=ExecutorConfig(
                    type=ExecutorType.SHELL,
                    command="echo 'Hello from scheduler'"
                ),
                priority=TaskPriority.NORMAL
            )
            assert task_shell.name == "测试Shell任务"
            assert task_shell.executor.type == ExecutorType.SHELL
            print(f"✅ Shell 任务创建成功: {task_shell.task_id}")
            
            # 测试 2.2: MCP 工具执行器任务
            print("\n[2.2] 创建 MCP 工具执行器任务...")
            task_mcp = TaskConfig(
                name="小红书搜索任务",
                description="定时搜索小红书活动",
                trigger=TriggerConfig(
                    type=TriggerType.DAILY,
                    time="09:00:00"
                ),
                executor=ExecutorConfig(
                    type=ExecutorType.MCP_TOOL,
                    tool_name="XHSSearchAgent",
                    tool_params={
                        "keywords": ["citywalk", "展览"],
                        "city": "上海"
                    }
                ),
                priority=TaskPriority.HIGH
            )
            assert task_mcp.executor.type == ExecutorType.MCP_TOOL
            assert task_mcp.executor.tool_name == "XHSSearchAgent"
            print(f"✅ MCP 工具任务创建成功: {task_mcp.task_id}")
            
            # 测试 2.3: HTTP 执行器任务
            print("\n[2.3] 创建 HTTP 执行器任务...")
            task_http = TaskConfig(
                name="健康检查任务",
                description="定时检查服务健康状态",
                trigger=TriggerConfig(
                    type=TriggerType.FIXED_RATE,
                    interval_seconds=300
                ),
                executor=ExecutorConfig(
                    type=ExecutorType.HTTP,
                    url="http://localhost:8000/health",
                    method="GET"
                )
            )
            assert task_http.executor.type == ExecutorType.HTTP
            print(f"✅ HTTP 任务创建成功: {task_http.task_id}")
            
            # 测试 2.4: 任务序列化
            print("\n[2.4] 测试任务序列化...")
            task_dict = task_shell.model_dump()
            assert "task_id" in task_dict
            assert "trigger" in task_dict
            assert "executor" in task_dict
            print(f"✅ 任务序列化成功 ({len(task_dict)} 个字段)")
            
            print("\n✅ 阶段 2 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 2 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_scheduler_basic(self) -> bool:
        """
        阶段 3: 调度器基本功能测试
        
        测试内容：
        - 注册任务
        - 列出任务
        - 获取任务详情
        - 暂停/恢复任务
        - 注销任务
        """
        print("\n" + "="*60)
        print("阶段 3: 调度器基本功能测试 (Scheduler)")
        print("="*60)
        
        try:
            # 测试 3.1: 注册任务
            print("\n[3.1] 注册任务...")
            task = TaskConfig(
                name="测试任务1",
                description="用于测试的简单任务",
                trigger=TriggerConfig(
                    type=TriggerType.FIXED_RATE,
                    interval_seconds=60
                ),
                executor=ExecutorConfig(
                    type=ExecutorType.SHELL,
                    command="echo 'test'"
                )
            )
            
            task_id = self.scheduler.register_task(task)
            assert task_id == task.task_id
            print(f"✅ 任务注册成功: {task_id}")
            
            # 测试 3.2: 列出任务
            print("\n[3.2] 列出所有任务...")
            tasks = self.scheduler.list_tasks()
            assert len(tasks) >= 1
            assert any(t.task_id == task_id for t in tasks)
            print(f"✅ 找到 {len(tasks)} 个任务")
            
            # 测试 3.3: 获取任务详情
            print("\n[3.3] 获取任务详情...")
            retrieved_task = self.scheduler.get_task(task_id)
            assert retrieved_task is not None
            assert retrieved_task.name == "测试任务1"
            print(f"✅ 任务详情获取成功: {retrieved_task.name}")
            
            # 测试 3.4: 获取任务状态
            print("\n[3.4] 获取任务状态...")
            status = self.scheduler.get_task_status(task_id)
            assert status is not None
            assert status["task_id"] == task_id
            assert "status" in status
            assert "next_run" in status
            print(f"✅ 任务状态: {status['status']}")
            
            # 测试 3.5: 暂停任务
            print("\n[3.5] 暂停任务...")
            success = self.scheduler.pause_task(task_id)
            assert success
            paused_task = self.scheduler.get_task(task_id)
            assert paused_task.status == TaskStatus.PAUSED
            assert not paused_task.enabled
            print(f"✅ 任务已暂停")
            
            # 测试 3.6: 恢复任务
            print("\n[3.6] 恢复任务...")
            success = self.scheduler.resume_task(task_id)
            assert success
            resumed_task = self.scheduler.get_task(task_id)
            assert resumed_task.status == TaskStatus.PENDING
            assert resumed_task.enabled
            print(f"✅ 任务已恢复")
            
            # 测试 3.7: 注销任务
            print("\n[3.7] 注销任务...")
            success = self.scheduler.unregister_task(task_id)
            assert success
            deleted_task = self.scheduler.get_task(task_id)
            assert deleted_task is None
            print(f"✅ 任务已注销")
            
            print("\n✅ 阶段 3 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 3 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_task_execution(self) -> bool:
        """
        阶段 4: 任务执行测试
        
        测试内容：
        - 手动触发任务
        - 执行记录
        - Shell 命令执行
        """
        print("\n" + "="*60)
        print("阶段 4: 任务执行测试")
        print("="*60)
        
        try:
            # 测试 4.1: 创建并注册任务
            print("\n[4.1] 创建测试任务...")
            task = TaskConfig(
                name="Echo测试任务",
                description="执行echo命令",
                trigger=TriggerConfig(
                    type=TriggerType.ONCE,
                    run_at=datetime.now() + timedelta(hours=1)
                ),
                executor=ExecutorConfig(
                    type=ExecutorType.SHELL,
                    command="echo 'Scheduler test execution'"
                ),
                timeout_seconds=10
            )
            
            task_id = self.scheduler.register_task(task)
            print(f"✅ 任务创建成功: {task_id}")
            
            # 测试 4.2: 手动触发任务
            print("\n[4.2] 手动触发任务...")
            record = self.scheduler.trigger_task(task_id)
            
            if record:
                print(f"✅ 任务执行完成")
                print(f"   状态: {record.status.value}")
                print(f"   耗时: {record.duration_seconds:.2f} 秒")
                if record.result:
                    print(f"   结果: {str(record.result)[:100]}")
                if record.error_message:
                    print(f"   错误: {record.error_message}")
            else:
                print("⚠️  任务执行失败")
            
            # 测试 4.3: 获取执行历史
            print("\n[4.3] 获取执行历史...")
            history = self.scheduler.get_execution_history(task_id, limit=10)
            assert len(history) >= 1
            print(f"✅ 找到 {len(history)} 条执行记录")
            
            for i, rec in enumerate(history[:3], 1):
                print(f"   [{i}] {rec.status.value} - {rec.started_at}")
            
            # 清理
            self.scheduler.unregister_task(task_id)
            
            print("\n✅ 阶段 4 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 4 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_scheduler_api(self) -> bool:
        """
        阶段 5: API 接口测试
        
        测试内容：
        - 创建任务 API
        - 列出任务 API
        - 获取状态 API
        - 触发任务 API
        - 删除任务 API
        """
        print("\n" + "="*60)
        print("阶段 5: API 接口测试 (SchedulerAPI)")
        print("="*60)
        
        try:
            # 测试 5.1: 获取示例配置
            print("\n[5.1] 获取示例配置...")
            result = scheduler_action("get_examples")
            assert result["success"]
            assert "examples" in result
            print(f"✅ 获取到 {len(result['examples'])} 个示例配置")
            
            # 测试 5.2: 创建任务
            print("\n[5.2] 通过 API 创建任务...")
            task_config = {
                "name": "API测试任务",
                "description": "通过API创建的测试任务",
                "trigger": {
                    "type": "fixed_rate",
                    "interval_seconds": 120
                },
                "executor": {
                    "type": "shell",
                    "command": "echo 'API test'"
                }
            }
            
            result = scheduler_action("create_task", task_config=task_config)
            assert result["success"]
            task_id = result["task_id"]
            print(f"✅ 任务创建成功: {task_id}")
            
            # 测试 5.3: 列出任务
            print("\n[5.3] 列出所有任务...")
            result = scheduler_action("list_tasks")
            assert result["success"]
            assert result["count"] >= 1
            print(f"✅ 找到 {result['count']} 个任务")
            
            # 测试 5.4: 获取任务状态
            print("\n[5.4] 获取任务状态...")
            result = scheduler_action("get_status", task_id=task_id)
            assert result["success"]
            assert result["status"]["task_id"] == task_id
            print(f"✅ 任务状态: {result['status']['status']}")
            
            # 测试 5.5: 暂停任务
            print("\n[5.5] 暂停任务...")
            result = scheduler_action("pause_task", task_id=task_id)
            assert result["success"]
            print(f"✅ {result['message']}")
            
            # 测试 5.6: 恢复任务
            print("\n[5.6] 恢复任务...")
            result = scheduler_action("resume_task", task_id=task_id)
            assert result["success"]
            print(f"✅ {result['message']}")
            
            # 测试 5.7: 删除任务
            print("\n[5.7] 删除任务...")
            result = scheduler_action("delete_task", task_id=task_id)
            assert result["success"]
            print(f"✅ {result['message']}")
            
            # 测试 5.8: 获取调度器统计
            print("\n[5.8] 获取调度器统计...")
            result = scheduler_action("get_scheduler_stats")
            assert result["success"]
            stats = result["stats"]
            print(f"✅ 调度器统计:")
            print(f"   总任务数: {stats['total_tasks']}")
            print(f"   启用任务数: {stats['enabled_tasks']}")
            print(f"   运行中任务: {stats['running_tasks']}")
            
            print("\n✅ 阶段 5 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 5 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """主测试函数"""
    print("="*60)
    print("🚀 调度器模块测试")
    print("="*60)
    
    tester = SchedulerTester()
    tester.setup()
    
    try:
        # 按顺序执行测试
        tests = [
            ("触发器配置", tester.test_trigger_config),
            ("任务配置", tester.test_task_config),
            ("调度器基本功能", tester.test_scheduler_basic),
            ("任务执行", tester.test_task_execution),
            ("API 接口", tester.test_scheduler_api),
        ]
        
        results = []
        for test_name, test_func in tests:
            result = test_func()
            results.append((test_name, result))
        
        # 打印测试总结
        print("\n" + "="*60)
        print("测试总结")
        print("="*60)
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = "✅ 通过" if result else "❌ 失败"
            print(f"{test_name}: {status}")
        
        print("="*60)
        print(f"总计: {passed}/{total} 通过")
        
        if passed == total:
            print("✨ 所有测试通过！")
            return True
        else:
            print(f"⚠️  {total - passed} 个测试失败")
            return False
        
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        tester.cleanup()


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(1)
