---
name: task-executor
description: TaskService LLM 的能力定义，用于执行复杂任务和工具链调用
version: 1.0.0
---

# Task Executor Skill

任务执行器的核心能力，专注于后台任务执行和工具链调用。

## 核心能力

### 1. 工具链执行
TaskService LLM 具备完整的工具链调用能力：
- 自动规划工具调用顺序
- 处理工具调用结果
- 支持多轮工具调用循环
- 最大迭代次数：10 次

### 2. 任务类型

#### 一次性任务 (TriggerType.ONCE)
默认的任务执行模式，立即执行一次：
- 用户请求的即时任务
- 聊天 LLM 委派的任务
- 手动触发的任务

#### 定时任务 (Scheduled)
支持解析为调度器任务：
- `fixed_delay`: 固定延迟
- `fixed_rate`: 固定速率
- `daily`: 每日定时
- `weekly`: 每周定时
- `monthly`: 每月定时
- `cron`: Cron 表达式

### 3. 可用工具

#### SearchAgent
网页搜索工具，基于 SerpApi。
- 输入: `query` (string) - 搜索关键词
- 输出: 搜索结果

#### SchedulerAgent
任务调度器，用于创建和管理定时任务。
详见 `references/scheduler-contracts.md`

## 执行流程

### 一次性任务执行流程
```
1. 接收任务描述
2. 分析所需工具
3. 执行工具链（最多 10 次迭代）
4. 返回执行结果
5. 通知用户完成
```

### 定时任务创建流程
```
1. 解析任务描述中的时间信息
2. 构建 TaskConfig
3. 注册到调度器
4. 返回任务 ID
5. 通知用户任务已安排
```

## 工具调用规则

### 工具链处理
- 每次工具调用后分析结果
- 决定是否需要继续调用
- 达到最大迭代次数时停止
- 返回最终汇总结果

### 错误处理
- 工具调用失败时记录错误
- 尝试替代方案
- 最终失败时通知用户

## 任务配置示例

### 一次性搜索任务
```json
{
  "task_type": "once",
  "description": "搜索上海周末活动",
  "tools": ["SearchAgent"],
  "parameters": {
    "query": "上海 周末 活动 展览"
  }
}
```

### 每周定时任务
```json
{
  "task_type": "scheduled",
  "description": "每周一搜索本周活动",
  "trigger": {
    "type": "weekly",
    "weekdays": [1],
    "time": "09:00:00"
  },
  "executor": {
    "type": "mcp_tool",
    "tool_name": "SearchAgent",
    "tool_params": {
      "query": "上海 本周 活动"
    }
  }
}
```

## 参考文档

- `references/scheduler-contracts.md` - 调度器工具合约
- `references/tool-contracts.md` - 工具合约定义
