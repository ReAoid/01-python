# Skills 架构说明

## 概述

Skills 是一种通过 Markdown 文件定义 LLM 能力的机制。通过修改不同的 SKILL.md 文件，可以控制不同 LLM 实例的行为和能力。

## 目录结构

```
backend/utils/skills/
├── __init__.py           # 模块导出
├── loader.py             # Skill 加载器
├── README.md             # 本文档
├── chat/                 # 聊天 LLM 的 skill
│   └── SKILL.md
├── task/                 # TaskService LLM 的 skill
│   ├── SKILL.md
│   └── references/
│       ├── tool-contracts.md
│       └── scheduler-contracts.md
└── lingyi-mcp-assistant/ # MCP 工具使用指南
    ├── SKILL.md
    └── references/
        ├── tool-contracts.md
        └── scheduler-contracts.md
```

## Skill 文件格式

每个 skill 目录必须包含一个 `SKILL.md` 文件，格式如下：

```markdown
---
name: skill-name
description: Skill 描述
version: 1.0.0
---

# Skill 标题

Skill 的详细内容...
```

### Frontmatter 字段

| 字段 | 必填 | 说明 |
|------|------|------|
| name | 是 | Skill 的唯一标识符 |
| description | 是 | Skill 的简短描述 |
| version | 否 | 版本号，默认 1.0.0 |

### References 目录

可选的 `references/` 目录用于存放参考文档，这些文档会被自动加载并附加到 skill 提示词中。

## 使用方式

### 1. 在 LLMClient 中使用

```python
from backend.utils.llm.llm_client import LLMClient

# 创建使用 chat skill 的客户端
client = LLMClient(
    system_prompt="自定义提示词",
    skill_name="chat",
    enable_tools=True
)
```

### 2. 在 TaskService 中使用

TaskService 自动加载 `task` skill：

```python
from backend.services.task_service import get_task_service

task_service = get_task_service()
result = await task_service.execute_once_task("搜索上海周末活动")
```

### 3. 直接使用 SkillLoader

```python
from backend.utils.skills.loader import get_skill_loader

loader = get_skill_loader()

# 列出所有 skill
skills = loader.list_skills()

# 加载特定 skill
skill = loader.load_skill("task")

# 获取完整的 skill 提示词（包含 references）
prompt = loader.get_skill_prompt("task")
```

## Skill 定义

### chat (聊天助手)

用于日常对话的 LLM，具备以下能力：
- 自然对话
- 简单工具调用（SearchAgent）
- 任务识别与委派

### task (任务执行器)

用于后台任务执行的 LLM，具备以下能力：
- 工具链执行（最多 10 次迭代）
- 一次性任务执行（TriggerType.ONCE）
- 定时任务创建

### lingyi-mcp-assistant (MCP 工具指南)

通用的 MCP 工具使用指南，定义工具调用规则。

## 任务执行流程

### 一次性任务 (TriggerType.ONCE)

```
用户请求 → 聊天 LLM 识别任务 → 委派给 TaskService
                                    ↓
                            TaskService 执行
                                    ↓
                            工具链调用（如需要）
                                    ↓
                            返回结果 → 通知用户
```

### 定时任务

```
用户请求 → 聊天 LLM 识别定时任务 → 委派给 TaskService
                                        ↓
                                TaskService 解析时间信息
                                        ↓
                                创建 TaskConfig
                                        ↓
                                注册到 Scheduler
                                        ↓
                                返回任务 ID → 通知用户
```

## 扩展 Skill

要添加新的 skill：

1. 在 `backend/utils/skills/` 下创建新目录
2. 创建 `SKILL.md` 文件，包含 frontmatter 和内容
3. 可选：创建 `references/` 目录存放参考文档
4. 在代码中通过 `skill_name` 参数使用新 skill
