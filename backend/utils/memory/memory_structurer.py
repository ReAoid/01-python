"""
记忆结构化处理器
实现两阶段记忆处理流程

阶段1：Session 总结生成
- 在会话结束时，将完整对话压缩为高质量总结
- 提取关键要点
- 存储到 SessionSummaryStore

阶段2：定期结构化处理
- 对未处理的会话总结进行深度分析
- 提取结构化记忆项 (MemoryItem)
- 自动分类和建立关联
- 存储到 MemoryItemStore 和 MemoryGraph
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import re
import json
from loguru import logger

from backend.core.llm import Llm
from backend.core.message import Message
from backend.config.settings import settings
from .memory_item import MemoryItem, MemoryType, SessionSummary
from .memory_store import SessionSummaryStore, MemoryItemStore
from .memory_category import CategoryManager
from .memory_graph import MemoryGraph


class MemoryStructurer:
    """
    记忆结构化处理器
    
    负责两阶段处理流程：
    1. 生成高质量的会话总结
    2. 从总结中提取结构化记忆项
    """
    
    def __init__(
        self,
        llm: Llm,
        summary_store: SessionSummaryStore,
        item_store: MemoryItemStore,
        category_manager: CategoryManager,
        memory_graph: MemoryGraph
    ):
        self.llm = llm
        self.summary_store = summary_store
        self.item_store = item_store
        self.category_manager = category_manager
        self.memory_graph = memory_graph
        
        # 配置
        self.structuring_batch_size = settings.memory.structuring_batch_size
        self.min_summaries_for_structuring = settings.memory.min_summaries_for_structuring
        
        # 会话原始对话存储目录
        self.sessions_dir = Path(self.summary_store.storage_dir) / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
    
    # =========================================================================
    # 阶段1：会话总结生成
    # =========================================================================
    
    def _save_raw_conversation(self, history: List[Message], session_id: str):
        """
        保存原始对话记录到文件
        
        Args:
            history: 完整的对话历史
            session_id: 会话ID
        """
        try:
            # 构造文件路径
            session_file = self.sessions_dir / f"{session_id}.json"
            
            # 转换消息为可序列化的格式
            conversation_data = {
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "message_count": len(history),
                "messages": [
                    {
                        "role": msg.role,
                        "content": msg.content,
                        "timestamp": getattr(msg, 'timestamp', None)
                    }
                    for msg in history
                ]
            }
            
            # 保存到文件
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(conversation_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"原始对话已保存: {session_file}")
            
        except Exception as e:
            logger.error(f"保存原始对话失败: {e}")
    
    async def generate_session_summary(
        self, 
        history: List[Message],
        session_id: str
    ) -> Optional[SessionSummary]:
        """
        阶段1：生成会话总结
        
        将完整的对话历史压缩为高质量的总结和关键要点
        在总结之前，会先保存原始对话记录到sessions文件夹
        
        Args:
            history: 完整的对话历史
            session_id: 会话ID
        
        Returns:
            SessionSummary 对象，如果失败则返回 None
        """
        if not history:
            logger.warning("对话历史为空，跳过总结")
            return None
        
        # 先保存原始对话记录
        self._save_raw_conversation(history, session_id)
        
        # 过滤 system 消息，构造对话文本
        conversation_text = "\n".join([
            f"{msg.role}: {msg.content}" 
            for msg in history 
            if msg.role != "system"
        ])
        
        # 构造总结 Prompt
        prompt = self._build_summary_prompt(conversation_text)
        
        try:
            messages = [
                Message(role="system", content="You are a skilled conversation analyst. Extract key information concisely."),
                Message(role="user", content=prompt)
            ]
            
            response = await self.llm.agenerate(messages)
            content = response.content.strip()
            
            # 解析响应
            summary_text, key_points = self._parse_summary_response(content)
            
            if not summary_text:
                logger.warning("未能生成有效总结")
                return None
            
            # 创建 SessionSummary
            session_summary = SessionSummary(
                session_id=session_id,
                summary=summary_text,
                key_points=key_points,
                message_count=len(history)
            )
            
            # 存储
            self.summary_store.add(session_summary)
            
            logger.info(f"会话总结生成成功: {len(summary_text)} 字符, {len(key_points)} 个要点")
            
            # 检查是否需要触发结构化处理
            await self._check_structuring_trigger()
            
            return session_summary
            
        except Exception as e:
            logger.error(f"生成会话总结失败: {e}")
            return None
    
    def _build_summary_prompt(self, conversation_text: str) -> str:
        """构造总结 Prompt"""
        return f"""Analyze this conversation and create a comprehensive summary.

CONVERSATION:
{conversation_text}

TASKS:
1. Write a concise summary (2-4 sentences) capturing the main topics and context
2. Extract 3-8 KEY POINTS about the user - focus on:
   - Personal facts (name, location, occupation)
   - Preferences and habits
   - Goals and plans
   - Relationships mentioned
   - Skills or expertise
   - Opinions and attitudes

OUTPUT FORMAT:
SUMMARY:
<your summary here>

KEY_POINTS:
- <point 1>
- <point 2>
- <point 3>
...

RULES:
- Only extract USER-related information
- Ignore greetings and pleasantries
- Be specific and factual
- If no significant information, write "No significant user information"
"""
    
    def _parse_summary_response(self, response: str) -> tuple:
        """解析总结响应"""
        summary = ""
        key_points = []
        
        # 提取 SUMMARY 部分
        summary_match = re.search(
            r'SUMMARY:\s*(.*?)(?:KEY_POINTS:|$)', 
            response, 
            re.DOTALL | re.IGNORECASE
        )
        if summary_match:
            summary = summary_match.group(1).strip()
        
        # 提取 KEY_POINTS 部分
        points_match = re.search(
            r'KEY_POINTS:\s*(.*?)$', 
            response, 
            re.DOTALL | re.IGNORECASE
        )
        if points_match:
            points_text = points_match.group(1)
            for line in points_text.split('\n'):
                line = line.strip()
                if line.startswith('-'):
                    point = line[1:].strip()
                    if point and "no significant" not in point.lower():
                        key_points.append(point)
        
        return summary, key_points
    
    async def _check_structuring_trigger(self):
        """检查是否需要触发结构化处理"""
        unstructured = self.summary_store.get_unstructured()
        
        if len(unstructured) >= self.min_summaries_for_structuring:
            logger.info(f"检测到 {len(unstructured)} 个未处理总结，触发结构化处理")
            await self.structure_pending_summaries()
    
    # =========================================================================
    # 阶段2：结构化处理
    # =========================================================================
    
    async def structure_pending_summaries(self) -> List[MemoryItem]:
        """
        阶段2：处理待结构化的会话总结
        
        从累积的总结中提取结构化记忆项，建立分类和关联
        
        Returns:
            提取的所有记忆项
        """
        unstructured = self.summary_store.get_unstructured()
        
        if not unstructured:
            logger.info("没有待处理的总结")
            return []
        
        # 取最早的一批处理
        batch = unstructured[:self.structuring_batch_size]
        logger.info(f"开始结构化处理 {len(batch)} 个总结...")
        
        all_items = []
        
        for summary in batch:
            items = await self._structure_single_summary(summary)
            all_items.extend(items)
        
        # 建立记忆项之间的关联
        if len(all_items) > 1:
            await self._build_item_relations(all_items)
        
        logger.info(f"结构化处理完成: 提取了 {len(all_items)} 个记忆项")
        return all_items
    
    async def _structure_single_summary(
        self, 
        summary: SessionSummary
    ) -> List[MemoryItem]:
        """
        结构化处理单个会话总结
        
        Args:
            summary: 会话总结
        
        Returns:
            提取的记忆项列表
        """
        # 合并总结和要点作为输入
        input_text = f"Summary: {summary.summary}\n\nKey Points:\n"
        input_text += "\n".join([f"- {p}" for p in summary.key_points])
        
        prompt = self._build_extraction_prompt(input_text)
        
        try:
            messages = [
                Message(role="system", content="You are a memory extraction specialist. Convert summaries into structured memory items."),
                Message(role="user", content=prompt)
            ]
            
            response = await self.llm.agenerate(messages)
            
            # 解析提取的记忆项
            items = self._parse_extraction_response(
                response.content, 
                summary.id,
                summary.session_id
            )
            
            if not items:
                logger.info(f"总结 {summary.id} 未提取到有效记忆项")
                summary.mark_structured([])
                return []
            
            # 分类和存储
            item_ids = []
            for item in items:
                # 自动分类
                self.category_manager.auto_categorize(item)
                
                # 添加到图谱
                self.memory_graph.add_node(item.id)
                
                # 存储
                self.item_store.add(item)
                item_ids.append(item.id)
            
            # 标记总结已处理
            summary.mark_structured(item_ids)
            self.summary_store._do_save()
            
            logger.info(f"总结 {summary.id} 提取了 {len(items)} 个记忆项")
            return items
            
        except Exception as e:
            logger.error(f"结构化处理失败: {e}")
            return []
    
    def _build_extraction_prompt(self, input_text: str) -> str:
        """构造记忆提取 Prompt"""
        return f"""Extract structured memory items from this session summary.

INPUT:
{input_text}

TASK:
Convert each piece of information into a structured memory item with:
- content: A clear, standalone statement (1-2 sentences)
- type: One of [preference, fact, experience, skill, opinion, relationship, habit, goal]
- importance: 0.0-1.0 (how important is this to remember?)
- tags: 1-3 relevant keywords

OUTPUT FORMAT (JSON array):
[
  {{
    "content": "The user likes drinking coffee in the morning",
    "type": "preference",
    "importance": 0.7,
    "tags": ["coffee", "morning routine"]
  }},
  ...
]

RULES:
- Each item should be self-contained and understandable alone
- Use third person ("The user..." or "User's...")
- Be specific, avoid vague statements
- Importance: 0.9+ for identity/core preferences, 0.5-0.8 for general info, <0.5 for trivial
- Return empty array [] if no valid memories
"""
    
    def _parse_extraction_response(
        self, 
        response: str,
        source_summary_id: str,
        source_session_id: str
    ) -> List[MemoryItem]:
        """解析提取响应"""
        items = []
        
        # 提取 JSON 数组
        json_match = re.search(r'\[.*\]', response, re.DOTALL)
        if not json_match:
            logger.warning("未找到有效的 JSON 数组")
            return []
        
        try:
            data = json.loads(json_match.group(0))
            
            for item_data in data:
                try:
                    # 验证必要字段
                    if not item_data.get("content"):
                        continue
                    
                    # 解析记忆类型
                    type_str = item_data.get("type", "fact").lower()
                    try:
                        memory_type = MemoryType(type_str)
                    except ValueError:
                        memory_type = MemoryType.FACT
                    
                    # 创建记忆项
                    item = MemoryItem(
                        content=item_data["content"],
                        memory_type=memory_type,
                        importance=min(1.0, max(0.0, item_data.get("importance", 0.5))),
                        tags=item_data.get("tags", []),
                        source_summary_id=source_summary_id,
                        source_session_ids=[source_session_id]
                    )
                    
                    items.append(item)
                    
                except Exception as e:
                    logger.warning(f"解析单个记忆项失败: {e}")
                    continue
            
            return items
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            return []
    
    async def _build_item_relations(self, items: List[MemoryItem]):
        """
        建立记忆项之间的关联
        
        策略：
        1. 同分类关联
        2. 同类型关联
        3. 标签重叠关联
        """
        for i, item1 in enumerate(items):
            for item2 in items[i+1:]:
                # 策略1：同分类
                if item1.category and item1.category == item2.category:
                    self.memory_graph.link_by_category(item1, item2)
                
                # 策略2：标签重叠
                common_tags = set(item1.tags) & set(item2.tags)
                if common_tags:
                    weight = len(common_tags) * 0.2
                    self.memory_graph.add_bidirectional_edge(
                        item1.id, item2.id,
                        "semantic",
                        weight=min(0.8, weight)
                    )
        
        # 建立时间关联
        self.memory_graph.link_temporal(items)
    
    # =========================================================================
    # 检索增强
    # =========================================================================
    
    async def retrieve_with_context(
        self, 
        query: str, 
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        增强检索：返回记忆项及其关联上下文（异步版本，用于深度检索）
        
        Args:
            query: 查询文本
            top_k: 返回数量
        
        Returns:
            包含记忆项和关联上下文的字典
        """
        # 向量检索
        primary_items = self.item_store.search(query, top_k=top_k)
        
        if not primary_items:
            return {"items": [], "context": "", "related": []}
        
        # 查找关联记忆
        related_ids = set()
        for item in primary_items:
            related = self.memory_graph.find_related(item.id, max_depth=1)
            for rid, _, _ in related:
                related_ids.add(rid)
        
        # 获取关联记忆项
        related_items = []
        for rid in related_ids:
            if rid not in [i.id for i in primary_items]:
                related_item = self.item_store.get(rid)
                if related_item:
                    related_items.append(related_item)
        
        # 构建上下文文本
        context_lines = ["相关记忆:"]
        for item in primary_items:
            context_lines.append(f"- [{item.memory_type.value}] {item.content}")
        
        if related_items:
            context_lines.append("\n关联信息:")
            for item in related_items[:3]:
                context_lines.append(f"- {item.content}")
        
        return {
            "items": primary_items,
            "context": "\n".join(context_lines),
            "related": related_items[:3]
        }
    
    def get_memory_context_string(self, query: str, top_k: int = 3) -> str:
        """
        获取检索上下文字符串（同步版本，用于快速检索）
        
        Args:
            query: 查询文本
            top_k: 返回数量
        
        Returns:
            格式化的上下文字符串
        """
        items = self.item_store.search(query, top_k=top_k)
        
        if not items:
            return ""
        
        lines = ["相关历史记忆:"]
        for item in items:
            lines.append(f"- [{item.memory_type.value}] {item.content}")
        
        return "\n".join(lines)
