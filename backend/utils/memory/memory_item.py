"""
记忆项数据模型

数据流：
原始对话 → Session总结 → 结构化记忆项 → 多层记忆网络
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
import uuid


class MemoryType(str, Enum):
    """记忆类型枚举"""
    PREFERENCE = "preference"       # 用户偏好
    FACT = "fact"                   # 事实信息
    EXPERIENCE = "experience"       # 经历体验
    SKILL = "skill"                 # 技能知识
    OPINION = "opinion"             # 观点态度
    RELATIONSHIP = "relationship"   # 人际关系
    HABIT = "habit"                 # 习惯行为
    GOAL = "goal"                   # 目标愿望


class MemoryItem(BaseModel):
    """
    记忆项：从会话总结中提取的结构化记忆单元
    每个记忆项是一个独立的、可检索的信息单元
    """
    # 唯一标识
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    # 核心内容
    content: str                    # 记忆内容（简洁的陈述句）
    memory_type: MemoryType         # 记忆类型
    
    # 重要性和置信度
    importance: float = Field(default=0.5, ge=0.0, le=1.0)  # 重要性评分
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)  # 置信度
    
    # 分类信息
    category: Optional[str] = None  # 所属分类
    tags: List[str] = Field(default_factory=list)  # 标签
    
    # 时间信息
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    last_accessed: Optional[datetime] = None  # 上次访问时间
    access_count: int = 0  # 访问次数
    
    # 溯源信息
    source_summary_id: Optional[str] = None  # 来源的会话总结ID
    source_session_ids: List[str] = Field(default_factory=list)  # 来源的会话ID列表
    
    # 关联信息（记忆图谱）
    related_items: List[str] = Field(default_factory=list)  # 相关记忆项ID
    
    # 向量表示
    embedding: Optional[List[float]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "importance": self.importance,
            "confidence": self.confidence,
            "category": self.category,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "access_count": self.access_count,
            "source_summary_id": self.source_summary_id,
            "source_session_ids": self.source_session_ids,
            "related_items": self.related_items,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryItem":
        """从字典创建记忆项"""
        # 处理日期字段
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if isinstance(data.get("updated_at"), str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        if data.get("last_accessed") and isinstance(data["last_accessed"], str):
            data["last_accessed"] = datetime.fromisoformat(data["last_accessed"])
        
        # 处理枚举
        if isinstance(data.get("memory_type"), str):
            data["memory_type"] = MemoryType(data["memory_type"])
        
        return cls(**data)
    
    def mark_accessed(self):
        """标记被访问"""
        self.last_accessed = datetime.now()
        self.access_count += 1
    
    def update_content(self, new_content: str, confidence_boost: float = 0.05):
        """更新内容并提升置信度"""
        self.content = new_content
        self.updated_at = datetime.now()
        self.confidence = min(1.0, self.confidence + confidence_boost)
    
    def add_related(self, item_id: str):
        """添加关联记忆"""
        if item_id not in self.related_items:
            self.related_items.append(item_id)
    
    def to_search_text(self) -> str:
        """生成用于检索的文本"""
        return f"[{self.memory_type.value}] {self.content}"


class SessionSummary(BaseModel):
    """
    会话总结：对一个完整对话会话的总结
    
    这是第一阶段处理的输出，第二阶段会基于这些总结
    提取结构化的 MemoryItem
    """
    # 唯一标识
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str  # 对应的会话ID
    
    # 总结内容
    summary: str  # 会话总结文本
    key_points: List[str] = Field(default_factory=list)  # 关键要点列表
    
    # 元数据
    created_at: datetime = Field(default_factory=datetime.now)
    message_count: int = 0  # 原始消息数量
    
    # 处理状态
    is_structured: bool = False  # 是否已进行结构化处理
    structured_at: Optional[datetime] = None  # 结构化处理时间
    extracted_item_ids: List[str] = Field(default_factory=list)  # 提取的记忆项ID
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "summary": self.summary,
            "key_points": self.key_points,
            "created_at": self.created_at.isoformat(),
            "message_count": self.message_count,
            "is_structured": self.is_structured,
            "structured_at": self.structured_at.isoformat() if self.structured_at else None,
            "extracted_item_ids": self.extracted_item_ids,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionSummary":
        """从字典创建"""
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if data.get("structured_at") and isinstance(data["structured_at"], str):
            data["structured_at"] = datetime.fromisoformat(data["structured_at"])
        return cls(**data)
    
    def mark_structured(self, item_ids: List[str]):
        """标记已完成结构化处理"""
        self.is_structured = True
        self.structured_at = datetime.now()
        self.extracted_item_ids = item_ids
