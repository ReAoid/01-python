"""
记忆管理器

核心变更：
1. 取消即时存储 - 不再每次对话后立即存储
2. 会话级总结存储 - Session 结束时只保存总结
3. 定期结构化处理 - 将总结转化为多层结构化存储

数据流：
原始对话 → 短期记忆（滑动窗口）
         ↓ Session 结束
        会话总结 → SessionSummaryStore
                 ↓ 定期处理
                结构化记忆项 → MemoryItemStore + MemoryGraph
"""
import os
from typing import List, Optional, Tuple, Callable
import logging
from datetime import datetime, timezone, timedelta

from backend.core.message import Message
from backend.core.llm import Llm
from backend.utils.openai_llm import OpenaiLlm
from backend.config import settings, migration

from .short_term import ShortTermMemory
from .memory_item import MemoryItem, SessionSummary
from .memory_store import SessionSummaryStore, MemoryItemStore
from .memory_category import CategoryManager
from .memory_graph import MemoryGraph
from .memory_structurer import MemoryStructurer

logger = logging.getLogger(__name__)

# =========================================================================
# 工具函数
# =========================================================================

def generate_session_id() -> str:
    """
    生成唯一的 session_id（使用北京时间）
    
    格式: session_YYYY-MM-DD_HH-MM-SS
    例如: session_2026-01-12_15-23-36
    
    Returns:
        格式化的 session_id 字符串
    """
    beijing_tz = timezone(timedelta(hours=8))
    beijing_time = datetime.now(beijing_tz)
    return f"session_{beijing_time.strftime('%Y-%m-%d_%H-%M-%S')}"


class MemoryManager:
    """
    记忆管理器
    
    协调各个记忆模块，实现两阶段记忆处理：
    
    阶段1（实时）：
    - 维护短期记忆（滑动窗口）
    - Session 结束时生成总结并存储
    
    阶段2（后台）：
    - 定期将总结结构化为记忆项
    - 自动分类和建立关联
    - 构建记忆图谱
    
    检索：
    - 短期记忆：最近对话上下文
    - 长期记忆：结构化记忆项检索
    """
    
    def __init__(self, llm: Llm, storage_dir: str = None):
        """
        初始化记忆管理器
        
        Args:
            llm: LLM 实例，用于生成 embedding 和处理
            storage_dir: 存储目录路径
        """
        self.llm = llm
        
        # 存储目录
        if storage_dir:
            self.storage_dir = storage_dir
        else:
            self.storage_dir = migration.user_memory_dir
        
        # 确保目录存在
        os.makedirs(self.storage_dir, exist_ok=True)
        
        # 从配置读取 embedding 模型
        self.embedding_model = settings.memory.embedding_model
        
        # ============================================================
        # 初始化各个记忆模块
        # ============================================================
        
        # 1. 短期记忆（滑动窗口）- 用于对话上下文
        self.short_term = ShortTermMemory(
            max_messages=settings.memory.max_history_length * 2  # 用户+助手
        )
        
        # 2. 定义 embedding 函数
        embedding_func = self._create_embedding_func()
        
        # 3. 会话总结存储（阶段1输出）
        self.summary_store = SessionSummaryStore(storage_dir=self.storage_dir)
        
        # 4. 结构化记忆项存储（阶段2输出）
        self.item_store = MemoryItemStore(
            storage_dir=self.storage_dir,
            embedding_func=embedding_func
        )
        
        # 5. 分类管理器
        self.category_manager = CategoryManager(storage_dir=self.storage_dir)
        
        # 6. 记忆图谱
        self.memory_graph = MemoryGraph(storage_dir=self.storage_dir)
        
        # 7. 结构化处理器（核心）
        self.structurer = MemoryStructurer(
            llm=llm,
            summary_store=self.summary_store,
            item_store=self.item_store,
            category_manager=self.category_manager,
            memory_graph=self.memory_graph
        )
        
        # 统计
        self._session_count = 0
        
        logger.info(f"MemoryManager 初始化完成 (重构版)")
        logger.info(f"  - 存储目录: {self.storage_dir}")
        logger.info(f"  - 已有总结: {len(self.summary_store.summaries)}")
        logger.info(f"  - 已有记忆项: {len(self.item_store.items)}")
        logger.info(f"  - 分类数: {len(self.category_manager.categories)}")
    
    def _create_embedding_func(self) -> Optional[Callable[[str], List[float]]]:
        """
        创建 embedding 函数
        使用独立的 embedding API 配置
        """
        try:
            from openai import OpenAI
            
            # 使用独立的 embedding 配置
            embedding_api_key = settings.EMBEDDING_API_KEY
            embedding_base_url = settings.EMBEDDING_BASE_URL
            embedding_timeout = settings.api.embedding_timeout
            
            if not embedding_api_key or not embedding_base_url:
                logger.warning("Embedding API 配置不完整，长期记忆检索功能将受限")
                return None
            
            # 创建独立的 embedding 客户端
            embedding_client = OpenAI(
                api_key=embedding_api_key,
                base_url=embedding_base_url,
                timeout=embedding_timeout
            )
            
            def embedding_func(text: str) -> List[float]:
                try:
                    text = text.replace("\n", " ")
                    response = embedding_client.embeddings.create(
                        input=[text],
                        model=self.embedding_model
                    )
                    return response.data[0].embedding
                except Exception as e:
                    logger.error(f"生成 embedding 失败: {e}")
                    return []
            
            logger.info(f"Embedding 客户端初始化成功 (模型: {self.embedding_model})")
            return embedding_func
            
        except Exception as e:
            logger.error(f"创建 embedding 函数失败: {e}")
            return None
    
    # =========================================================================
    # 对话交互接口
    # =========================================================================
    
    def add_interaction(self, user_input: str, ai_output: str, metadata: dict = None):
        """
        添加一次交互记录
        
        重要变更：
        - 只更新短期记忆
        - 不再即时存储到向量数据库
        - 长期记忆由 Session 总结时统一处理
        
        Args:
            user_input: 用户输入
            ai_output: AI 回复
            metadata: 元数据（保留接口兼容，但不再使用）
        """
        # 只更新短期记忆
        self.short_term.add("user", user_input)
        self.short_term.add("assistant", ai_output)
        
        logger.debug(f"交互已添加到短期记忆 (不即时存储)")
    
    # =========================================================================
    # 阶段1：会话总结
    # =========================================================================
    
    async def summarize_session(
        self, 
        history: List[Message],
        session_id: str = None
    ) -> str:
        """
        阶段1：Session 结束时生成总结
        
        这是存储长期记忆的唯一入口。
        将完整对话压缩为高质量总结，存储到 SessionSummaryStore
        
        Args:
            history: 完整的对话历史
            session_id: 会话 ID
        
        Returns:
            总结文本（用于注入新会话的上下文）
        """
        if not history:
            return ""
        
        # 生成唯一的 session_id（使用北京时间）
        if not session_id:
            session_id = generate_session_id()
        
        # 调用结构化处理器生成总结
        summary = await self.structurer.generate_session_summary(history, session_id)
        
        if summary:
            logger.info(f"Session {session_id} 总结已存储")
            return summary.summary
        else:
            return ""
    
    # =========================================================================
    # 阶段2：结构化处理（可手动触发或自动触发）
    # =========================================================================
    
    async def process_pending_summaries(self) -> List[MemoryItem]:
        """
        阶段2：处理待结构化的总结
        
        可以手动调用，也会在总结累积到一定数量时自动触发
        
        Returns:
            新提取的记忆项列表
        """
        items = await self.structurer.structure_pending_summaries()
        return items
    
    # =========================================================================
    # 检索接口
    # =========================================================================
    
    def get_context(self, query: str, top_k: int = 3) -> Tuple[List[Message], str]:
        """
        获取构建 Prompt 所需的上下文
        
        Args:
            query: 用户当前的查询
            top_k: 检索长期记忆的数量
        
        Returns:
            (short_term_messages, long_term_context_string)
        """
        # 1. 获取短期记忆
        short_term_msgs = self.short_term.get_messages()
        
        # 2. 检索长期记忆（结构化记忆项）
        long_term_context = self.structurer.get_memory_context_string(query, top_k)
        
        return short_term_msgs, long_term_context
    
    async def get_enhanced_context(
        self, 
        query: str, 
        top_k: int = 5
    ) -> Tuple[List[Message], str, List[MemoryItem]]:
        """
        获取增强上下文（包含关联记忆）
        
        Args:
            query: 查询文本
            top_k: 返回数量
        
        Returns:
            (short_term_messages, context_string, related_items)
        """
        short_term_msgs = self.short_term.get_messages()
        
        result = await self.structurer.retrieve_with_context(query, top_k)
        
        return (
            short_term_msgs,
            result["context"],
            result["items"] + result["related"]
        )
    
    def clear(self):
        """清空短期记忆"""
        self.short_term.clear()
        logger.info("短期记忆已清空")
    
    def get_statistics(self) -> dict:
        """获取记忆系统统计信息"""
        return {
            "short_term": {
                "message_count": len(self.short_term.get_messages())
            },
            "summaries": {
                "total": len(self.summary_store.summaries),
                "unstructured": len(self.summary_store.get_unstructured())
            },
            "memory_items": self.item_store.get_statistics(),
            "categories": self.category_manager.get_statistics(),
            "graph": self.memory_graph.get_statistics()
        }
    
    def get_all_memories(self) -> List[MemoryItem]:
        """获取所有记忆项"""
        return list(self.item_store.items.values())
    
    def get_memories_by_category(self, category: str) -> List[MemoryItem]:
        """按分类获取记忆项"""
        return self.item_store.get_by_category(category)
    
    def get_recent_summaries(self, count: int = 10) -> List[SessionSummary]:
        """获取最近的会话总结"""
        return self.summary_store.get_recent(count)
