"""
触发器模块
计算任务的下次执行时间
"""

from datetime import datetime, timedelta
from typing import Optional
import calendar
from zoneinfo import ZoneInfo

from backend.utils.scheduler.models import TriggerConfig, TriggerType


class TriggerCalculator:
    """触发时间计算器"""
    
    @staticmethod
    def get_next_run_time(
        trigger: TriggerConfig,
        last_run_time: Optional[datetime] = None,
        last_run_duration: Optional[float] = None,
        base_time: Optional[datetime] = None
    ) -> Optional[datetime]:
        """
        计算下次执行时间
        
        Args:
            trigger: 触发配置
            last_run_time: 上次执行时间
            last_run_duration: 上次执行耗时（秒）
            base_time: 基准时间（默认当前时间）
        
        Returns:
            下次执行时间，None表示不再执行
        """
        tz = ZoneInfo(trigger.timezone)
        now = base_time or datetime.now(tz)
        if now.tzinfo is None:
            now = now.replace(tzinfo=tz)
        
        calculator = TriggerCalculator()
        
        if trigger.type == TriggerType.FIXED_DELAY:
            return calculator._calc_fixed_delay(trigger, last_run_time, last_run_duration, now)
        
        elif trigger.type == TriggerType.FIXED_RATE:
            return calculator._calc_fixed_rate(trigger, last_run_time, now)
        
        elif trigger.type == TriggerType.DAILY:
            return calculator._calc_daily(trigger, now)
        
        elif trigger.type == TriggerType.WEEKLY:
            return calculator._calc_weekly(trigger, now)
        
        elif trigger.type == TriggerType.MONTHLY:
            return calculator._calc_monthly(trigger, now)
        
        elif trigger.type == TriggerType.YEARLY:
            return calculator._calc_yearly(trigger, now)
        
        elif trigger.type == TriggerType.CRON:
            return calculator._calc_cron(trigger, now)
        
        elif trigger.type == TriggerType.ONCE:
            return calculator._calc_once(trigger, last_run_time, now)
        
        elif trigger.type == TriggerType.DELAY:
            return calculator._calc_delay(trigger, last_run_time, now)
        
        return None
    
    def _parse_time(self, time_str: str, tz: ZoneInfo) -> tuple:
        """解析时间字符串 HH:MM:SS"""
        parts = time_str.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        second = int(parts[2]) if len(parts) > 2 else 0
        return hour, minute, second
    
    def _calc_fixed_delay(
        self, 
        trigger: TriggerConfig, 
        last_run_time: Optional[datetime],
        last_run_duration: Optional[float],
        now: datetime
    ) -> datetime:
        """固定延迟：任务完成后等待N时间"""
        if last_run_time is None:
            return now
        
        # 任务完成时间 = 开始时间 + 执行耗时
        duration = last_run_duration or 0
        finish_time = last_run_time + timedelta(seconds=duration)
        next_time = finish_time + timedelta(seconds=trigger.interval_seconds)
        
        return max(next_time, now)
    
    def _calc_fixed_rate(
        self,
        trigger: TriggerConfig,
        last_run_time: Optional[datetime],
        now: datetime
    ) -> datetime:
        """固定速率：每隔N时间强制触发"""
        if last_run_time is None:
            return now
        
        next_time = last_run_time + timedelta(seconds=trigger.interval_seconds)
        
        # 如果已经过了下次执行时间，计算最近的下一个周期
        while next_time <= now:
            next_time += timedelta(seconds=trigger.interval_seconds)
        
        return next_time
    
    def _calc_daily(self, trigger: TriggerConfig, now: datetime) -> datetime:
        """每日触发"""
        tz = ZoneInfo(trigger.timezone)
        hour, minute, second = self._parse_time(trigger.time, tz)
        
        # 今天的执行时间
        today_run = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
        
        if today_run > now:
            return today_run
        else:
            # 明天
            return today_run + timedelta(days=1)
    
    def _calc_weekly(self, trigger: TriggerConfig, now: datetime) -> datetime:
        """每周触发"""
        tz = ZoneInfo(trigger.timezone)
        hour, minute, second = self._parse_time(trigger.time, tz)
        weekdays = sorted(trigger.weekdays)  # 1-7
        
        current_weekday = now.isoweekday()  # 1=周一, 7=周日
        
        # 今天的执行时间
        today_run = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
        
        # 检查今天是否在执行日列表中且时间未过
        if current_weekday in weekdays and today_run > now:
            return today_run
        
        # 找下一个执行日
        for day in weekdays:
            if day > current_weekday:
                days_ahead = day - current_weekday
                return today_run + timedelta(days=days_ahead)
        
        # 下周的第一个执行日
        days_ahead = 7 - current_weekday + weekdays[0]
        return today_run + timedelta(days=days_ahead)
    
    def _calc_monthly(self, trigger: TriggerConfig, now: datetime) -> datetime:
        """每月触发"""
        tz = ZoneInfo(trigger.timezone)
        hour, minute, second = self._parse_time(trigger.time, tz)
        target_day = trigger.day
        
        year = now.year
        month = now.month
        
        # 处理月末
        if target_day == -1:
            target_day = calendar.monthrange(year, month)[1]
        
        # 确保日期有效
        max_day = calendar.monthrange(year, month)[1]
        actual_day = min(target_day, max_day)
        
        # 本月的执行时间
        try:
            this_month_run = now.replace(
                day=actual_day, hour=hour, minute=minute, second=second, microsecond=0
            )
        except ValueError:
            # 日期无效，跳到下个月
            this_month_run = now
        
        if this_month_run > now:
            return this_month_run
        
        # 下个月
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1
        
        # 重新计算月末
        if trigger.day == -1:
            actual_day = calendar.monthrange(year, month)[1]
        else:
            max_day = calendar.monthrange(year, month)[1]
            actual_day = min(trigger.day, max_day)
        
        return datetime(year, month, actual_day, hour, minute, second, tzinfo=tz)

    def _calc_yearly(self, trigger: TriggerConfig, now: datetime) -> datetime:
        """每年触发"""
        tz = ZoneInfo(trigger.timezone)
        hour, minute, second = self._parse_time(trigger.time, tz)
        target_month = trigger.month
        target_day = trigger.day
        
        year = now.year
        
        # 处理月末
        if target_day == -1:
            target_day = calendar.monthrange(year, target_month)[1]
        
        # 今年的执行时间
        try:
            this_year_run = datetime(
                year, target_month, target_day, hour, minute, second, tzinfo=tz
            )
        except ValueError:
            # 日期无效（如2月30日），使用该月最后一天
            max_day = calendar.monthrange(year, target_month)[1]
            this_year_run = datetime(
                year, target_month, max_day, hour, minute, second, tzinfo=tz
            )
        
        if this_year_run > now:
            return this_year_run
        
        # 明年
        year += 1
        if target_day == -1 or trigger.day == -1:
            target_day = calendar.monthrange(year, target_month)[1]
        
        try:
            return datetime(year, target_month, target_day, hour, minute, second, tzinfo=tz)
        except ValueError:
            max_day = calendar.monthrange(year, target_month)[1]
            return datetime(year, target_month, max_day, hour, minute, second, tzinfo=tz)
    
    def _calc_cron(self, trigger: TriggerConfig, now: datetime) -> datetime:
        """Cron表达式触发"""
        try:
            from croniter import croniter
        except ImportError:
            raise ImportError("Cron触发需要安装 croniter: pip install croniter")
        
        tz = ZoneInfo(trigger.timezone)
        cron = croniter(trigger.cron_expr, now)
        return cron.get_next(datetime).replace(tzinfo=tz)
    
    def _calc_once(
        self, 
        trigger: TriggerConfig, 
        last_run_time: Optional[datetime],
        now: datetime
    ) -> Optional[datetime]:
        """一次性触发"""
        # 已经执行过，不再执行
        if last_run_time is not None:
            return None
        
        run_at = trigger.run_at
        if run_at.tzinfo is None:
            tz = ZoneInfo(trigger.timezone)
            run_at = run_at.replace(tzinfo=tz)
        
        # 时间已过，立即执行
        if run_at <= now:
            return now
        
        return run_at
    
    def _calc_delay(
        self,
        trigger: TriggerConfig,
        last_run_time: Optional[datetime],
        now: datetime
    ) -> Optional[datetime]:
        """延迟触发"""
        # 已经执行过，不再执行
        if last_run_time is not None:
            return None
        
        return now + timedelta(seconds=trigger.delay_seconds)


def get_missed_runs(
    trigger: TriggerConfig,
    last_run_time: datetime,
    current_time: datetime
) -> list[datetime]:
    """
    获取错过的执行时间列表
    
    Args:
        trigger: 触发配置
        last_run_time: 上次执行时间
        current_time: 当前时间
    
    Returns:
        错过的执行时间列表
    """
    missed = []
    calc = TriggerCalculator()
    
    # 从上次执行时间开始计算
    next_time = TriggerCalculator.get_next_run_time(
        trigger, last_run_time, None, last_run_time
    )
    
    while next_time and next_time < current_time:
        missed.append(next_time)
        next_time = TriggerCalculator.get_next_run_time(
            trigger, next_time, None, next_time
        )
        
        # 防止无限循环
        if len(missed) > 1000:
            break
    
    return missed
