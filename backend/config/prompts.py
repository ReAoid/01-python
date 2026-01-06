from dataclasses import dataclass


@dataclass(frozen=True)
class PromptTemplate:
    """
    提示词模板类
    
    用于管理带有命名占位符的提示词模板，支持动态内容注入。
    使用 Python 的字符串格式化语法（{variable_name}）定义占位符。
    
    属性:
        template: 包含占位符的提示词模板字符串
    
    示例:
        >>> prompt = PromptTemplate(template="你好，{name}！")
        >>> prompt.render(name="小明")
        '你好，小明！'
    """

    template: str

    def render(self, **kwargs) -> str:
        """
        渲染提示词模板，将占位符替换为实际值
        
        参数:
            **kwargs: 键值对参数，键名对应模板中的占位符名称
        
        返回:
            str: 渲染后的提示词字符串
        
        异常:
            ValueError: 当模板中的占位符在参数中未提供时抛出
        
        示例:
            >>> template.render(user_input="Python教程", action="研究")
        """
        try:
            return self.template.format(**kwargs)
        except KeyError as exc:
            missing = exc.args[0]
            raise ValueError(f"Missing variable in prompt template: {missing}") from exc


# ============================================================================
# 系统提示词（角色定义 / 人格设定）
# ============================================================================

# 默认聊天助手人格
# 用途: 为通用对话场景提供基础的助手角色定义
# 场景: 未指定特定角色时的默认对话模式
SYSTEM_PROMPT_DEFAULT_ASSISTANT = "You are a helpful AI assistant."

# 后台任务分析器人格
# 用途: 定义专门用于分析用户输入并识别潜在任务的角色
# 场景: TaskService 后台任务分析服务中使用
SYSTEM_PROMPT_TASK_ANALYZER = "You are a background task analyzer."

# 自我意识服务人格
# 用途: 定义具有自主思考能力的 AI 角色
# 场景: SelfAwarenessService 自我意识服务中使用，用于生成主动思考和探索
SYSTEM_PROMPT_SELF_AWARENESS = "You are a self-aware AI."

# 记忆对话分析师人格
# 用途: 定义专门用于分析对话内容并提取关键信息的角色
# 场景: 记忆系统中对会话进行总结和关键点提取时使用
SYSTEM_PROMPT_MEMORY_CONVERSATION_ANALYST = (
    "You are a skilled conversation analyst. Extract key information concisely."
)

# 记忆提取专家人格
# 用途: 定义将对话摘要转换为结构化记忆项的专家角色
# 场景: 记忆系统中将会话摘要转换为结构化存储格式时使用
SYSTEM_PROMPT_MEMORY_EXTRACTION_SPECIALIST = (
    "You are a memory extraction specialist. Convert summaries into structured memory items."
)

# 代码助手人格（示例）
# 用途: 定义专门编写 Python 代码的助手角色
# 场景: openai_llm 模块的演示示例中使用
SYSTEM_PROMPT_CODE_ASSISTANT = "You are a helpful assistant that writes Python code."


# ============================================================================
# 任务服务提示词
# ============================================================================

# 任务意图分析提示词
# 用途: 从用户输入中识别和提取可以在后台执行的潜在任务
# 场景: TaskService 分析用户消息，判断是否包含需要后台处理的任务
# 参数说明:
#   - user_input: 用户的原始输入文本
# 返回格式:
#   - 有任务: JSON 格式 {"task": "任务描述", "action": "任务类型"}
#   - 无任务: 字符串 "NO_TASK"
# 示例:
#   输入: "我想了解更多关于 Python 的知识"
#   输出: {"task": "研究 Python", "action": "research"}
TASK_PROMPT_ANALYZE_INTENT = PromptTemplate(
    template=(
        "Analyze the user's input for any latent actionable tasks that can be performed in the background.\n"
        "Examples: \"I wish I knew more about Python\" -> Research Python.\n"
        "\"Remind me to buy milk\" -> Set reminder.\n"
        "\n"
        "User Input: \"{user_input}\"\n"
        "\n"
        "If there is a clear task, describe it in JSON format: {{ \"task\": \"description\", \"action\": \"research|reminder|...\" }}.\n"
        "If no task, return \"NO_TASK\".\n"
    )
)


# ============================================================================
# 自我意识服务提示词
# ============================================================================

# 自主反思提示词
# 用途: 在系统空闲时触发 AI 的自主思考和探索行为
# 场景: SelfAwarenessService 在没有用户交互时生成内部独白和研究想法
# 参数说明:
#   - interests: AI 当前的兴趣领域或关注点
# 返回格式: 自由文本形式的内部独白、假设或研究任务
# 示例:
#   输入: interests="机器学习和自然语言处理"
#   输出: "我想探索一下注意力机制在对话理解中的具体应用..."
SELF_AWARENESS_PROMPT_REFLECTION = PromptTemplate(
    template=(
        "You are an autonomous AI with your own internal drive.\n"
        "The system is currently idle. Based on your interests: \"{interests}\",\n"
        "generate a thought, a hypothesis, or a small research task you want to explore.\n"
        "\n"
        "Output your internal monologue.\n"
    )
)


# ============================================================================
# 记忆结构化提示词（会话总结 & 记忆提取）
# ============================================================================

# 会话总结提示词
# 用途: 分析对话内容并生成结构化的会话摘要和关键点
# 场景: MemoryStructurer 在会话结束或定期处理时对对话历史进行总结
# 参数说明:
#   - conversation_text: 完整的对话文本，包含用户和助手的所有消息
# 返回格式:
#   SUMMARY: 2-4 句话的对话总结
#   KEY_POINTS: 关于用户的 3-8 个关键信息点列表
# 关注内容:
#   - 个人信息（姓名、地点、职业）
#   - 偏好和习惯
#   - 目标和计划
#   - 提及的人际关系
#   - 技能或专业知识
#   - 观点和态度
# 示例:
#   输入: 包含用户介绍自己喜欢编程和咖啡的对话
#   输出: SUMMARY 部分总结对话主题，KEY_POINTS 提取"用户喜欢 Python 编程"等要点
MEMORY_PROMPT_SESSION_SUMMARY = PromptTemplate(
    template=(
        "Analyze this conversation and create a comprehensive summary.\n\n"
        "CONVERSATION:\n"
        "{conversation_text}\n\n"
        "TASKS:\n"
        "1. Write a concise summary (2-4 sentences) capturing the main topics and context\n"
        "2. Extract 3-8 KEY POINTS about the user - focus on:\n"
        "   - Personal facts (name, location, occupation)\n"
        "   - Preferences and habits\n"
        "   - Goals and plans\n"
        "   - Relationships mentioned\n"
        "   - Skills or expertise\n"
        "   - Opinions and attitudes\n\n"
        "OUTPUT FORMAT:\n"
        "SUMMARY:\n"
        "<your summary here>\n\n"
        "KEY_POINTS:\n"
        "- <point 1>\n"
        "- <point 2>\n"
        "- <point 3>\n"
        "...\n\n"
        "RULES:\n"
        "- Only extract USER-related information\n"
        "- Ignore greetings and pleasantries\n"
        "- Be specific and factual\n"
        "- If no significant information, write \"No significant user information\"\n"
    )
)

# 记忆提取提示词
# 用途: 将会话摘要转换为结构化的记忆项，便于系统存储和检索
# 场景: MemoryStructurer 在获得会话总结后，将关键点转换为标准化的记忆对象
# 参数说明:
#   - input_text: 会话摘要文本，通常是 MEMORY_PROMPT_SESSION_SUMMARY 的输出结果
# 返回格式: JSON 数组，每个元素包含以下字段:
#   - content: 清晰独立的陈述（1-2 句话）
#   - type: 记忆类型，可选值 [preference, fact, experience, skill, opinion, relationship, habit, goal]
#   - importance: 重要性评分 0.0-1.0
#     * 0.9+: 身份信息或核心偏好
#     * 0.5-0.8: 一般信息
#     * <0.5: 琐碎信息
#   - tags: 1-3 个相关关键词标签
# 示例:
#   输入: "用户喜欢早上喝咖啡"
#   输出: [{"content": "The user likes drinking coffee in the morning", 
#           "type": "preference", "importance": 0.7, 
#           "tags": ["coffee", "morning routine"]}]
MEMORY_PROMPT_EXTRACTION = PromptTemplate(
    template=(
        "Extract structured memory items from this session summary.\n\n"
        "INPUT:\n"
        "{input_text}\n\n"
        "TASK:\n"
        "Convert each piece of information into a structured memory item with:\n"
        "- content: A clear, standalone statement (1-2 sentences)\n"
        "- type: One of [preference, fact, experience, skill, opinion, relationship, habit, goal]\n"
        "- importance: 0.0-1.0 (how important is this to remember?)\n"
        "- tags: 1-3 relevant keywords\n\n"
        "OUTPUT FORMAT (JSON array):\n"
        "[\n"
        "  {{\n"
        "    \"content\": \"The user likes drinking coffee in the morning\",\n"
        "    \"type\": \"preference\",\n"
        "    \"importance\": 0.7,\n"
        "    \"tags\": [\"coffee\", \"morning routine\"]\n"
        "  }},\n"
        "  ...\n"
        "]\n\n"
        "RULES:\n"
        "- Each item should be self-contained and understandable alone\n"
        "- Use third person (\"The user...\" or \"User's...\")\n"
        "- Be specific, avoid vague statements\n"
        "- Importance: 0.9+ for identity/core preferences, 0.5-0.8 for general info, <0.5 for trivial\n"
        "- Return empty array [] if no valid memories\n"
    )
)
