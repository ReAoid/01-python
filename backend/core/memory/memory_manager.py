import os
from typing import List, Optional, Tuple
from loguru import logger
from backend.core.message import Message
from backend.core.llm import Llm
from backend.openai_llm import OpenaiLlm
from backend.core.memory.short_term import ShortTermMemory
from backend.core.memory.vector_store import VectorStore

class MemoryManager:
    """
    记忆管理器。
    协调短期记忆（滑动窗口）和长期记忆（向量存储）。

    TODO: [架构改进]
    1. 反思机制 (Reflection)：定期回顾记忆并生成更高层级的见解 (Insights)，存回长期记忆。
    2. 多租户支持：支持多用户/多会话隔离 (Session/User isolation)。
    """

    def __init__(self, llm: Llm, vector_store_path: str = "memory_store.json"):
        """
        初始化记忆管理器。

        Args:
            llm: LLM 实例，用于生成 embedding 和摘要
            vector_store_path: 向量存储文件路径
        """
        self.llm = llm
        self.short_term = ShortTermMemory()
        
        # 确定 Embedding 模型
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        
        # 定义 embedding 函数
        def openai_embedding_func(text: str) -> List[float]:
            # TODO: [接口抽象] 抽象 Embedding 接口，支持多种 Provider (如 HuggingFace, Cohere, Ollama 本地模型)。
            if isinstance(llm, OpenaiLlm):
                try:
                    # 替换换行符以获得更好的 embedding
                    text = text.replace("\n", " ")
                    response = llm.client.embeddings.create(
                        input=[text],
                        model=self.embedding_model
                    )
                    return response.data[0].embedding
                except Exception as e:
                    logger.error(f"生成 Embedding 失败: {e}")
                    return []
            else:
                # TODO: 支持其他 LLM 提供商
                logger.warning("当前仅 OpenaiLlm 支持生成 Embedding，将跳过长期记忆功能")
                return []

        self.vector_store = VectorStore(
            file_path=vector_store_path,
            embedding_func=openai_embedding_func
        )
        
        logger.info("MemoryManager 初始化完成")

    def add_interaction(self, user_input: str, ai_output: str, metadata: dict = None):
        """
        添加一次交互记录。
        会自动更新短期记忆，并异步（这里简化为同步）更新长期记忆。

        Args:
            user_input: 用户输入
            ai_output: AI 回复
            metadata: 元数据

        TODO: [性能与策略]
        1. 异步处理：将长期记忆的 embedding 生成和存储放入后台任务 (asyncio.create_task 或 Celery)，避免阻塞当前对话响应。
        2. 智能筛选：引入 LLM 决策步骤 (Importance Filter)，判断当前的交互是否包含重要信息（如用户喜好、事实陈述），只有重要的信息才写入长期记忆，避免知识库被闲聊污染。
        """
        # 1. 更新短期记忆
        self.short_term.add("user", user_input)
        self.short_term.add("assistant", ai_output)
        
        # 2. 更新长期记忆 (可选：可以只存储重要信息，或者由 LLM 决定是否存储)
        # 这里为了简单，将用户输入和 AI 回复拼接存储，或者是分开存储
        # 策略：将 (User, AI) 对作为一个记忆单元存储
        interaction_text = f"User: {user_input}\nAssistant: {ai_output}"
        
        # 可以在这里加入 LLM 判断逻辑：这条交互值得记住吗？
        # 目前直接存入
        if self.vector_store.embedding_func:
            self.vector_store.add(interaction_text, metadata=metadata)

    def get_context(self, query: str, top_k: int = 3) -> Tuple[List[Message], str]:
        """
        获取构建 Prompt 所需的上下文。

        TODO: [检索增强]
        1. 查询改写：对原始 query 进行改写或扩展 (Query Expansion)，以提高检索命中率。
        2. 重排序 (Rerank)：检索出更多结果 (top_k * n)，然后使用 Cross-Encoder 进行精细排序。
        3. 动态参数：根据 query 的复杂度动态调整检索数量 (top_k)。

        Args:
            query: 用户当前的查询
            top_k: 检索长期记忆的数量

        Returns:
            (short_term_messages, long_term_context_string)
        """
        # 1. 获取短期记忆
        short_term_msgs = self.short_term.get_messages()
        
        # 2. 检索长期记忆
        long_term_context = ""
        if self.vector_store.embedding_func:
            results = self.vector_store.search(query, top_k=top_k)
            if results:
                context_parts = []
                for res in results:
                    context_parts.append(f"- {res['text']}")
                
                long_term_context = "相关历史记忆:\n" + "\n".join(context_parts)
        
        return short_term_msgs, long_term_context

    def clear(self):
        """清空所有记忆"""
        self.short_term.clear()
        # vector_store 是否清空取决于需求，通常长期记忆不清空
        # self.vector_store.documents = [] 
        # self.vector_store.save()

