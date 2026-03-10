# Tool Contracts

TaskService 可用的工具合约定义。

## Discovery Rule

工具列表取决于 `backend/utils/mcp/plugins/**/manifest.json` 中的定义。

## Current Tools

### SearchAgent
网页搜索工具，基于 SerpApi。

- Name: `SearchAgent`
- Input:
  - `query` (`string`, required): 搜索关键词
- Output:
  - String payload (JSON string) 包含搜索结果
- Dependency:
  - `third_party_api.serpapi_api_key` in `backend/config/core_config.json`

### SchedulerAgent
任务调度器，用于创建和管理定时任务。

- Name: `SchedulerAgent`
- Input:
  - `action` (`string`, required): 操作类型
  - `task_id` (`string`, optional): 任务 ID
  - `task_config` (`object`, optional): 任务配置
- Output:
  - JSON string 包含操作结果

## Error Patterns

当输出以下内容开头时视为错误：
- `错误:`
- `error:`
- `调用工具`

## Operational Notes

- 工具返回纯文本或 JSON 格式文本
- 如果 SerpApi 未配置，返回配置指导而非重试
