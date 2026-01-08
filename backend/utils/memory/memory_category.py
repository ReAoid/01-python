"""
记忆分类管理器

分类类型：
1. 系统分类 - 预定义的通用分类
2. 自动分类 - 基于记忆类型自动归类
3. 动态分类 - 基于内容聚类生成
"""
from typing import List, Dict, Optional, Any
from datetime import datetime
from pathlib import Path
import json
import logging

from backend.config import paths
from .memory_item import MemoryItem, MemoryType

logger = logging.getLogger(__name__)

# 系统预定义分类
SYSTEM_CATEGORIES = {
    "personal_info": {
        "name": "个人信息",
        "description": "用户的基本信息，如姓名、年龄、职业等",
        "keywords": ["姓名", "年龄", "职业", "住址", "身份"]
    },
    "preferences": {
        "name": "偏好喜好",
        "description": "用户的喜好和偏好设置",
        "keywords": ["喜欢", "讨厌", "偏好", "最爱", "习惯"]
    },
    "work_life": {
        "name": "工作生活",
        "description": "工作相关信息和日常生活",
        "keywords": ["工作", "公司", "项目", "任务", "日程"]
    },
    "relationships": {
        "name": "人际关系",
        "description": "用户的社交关系和人际网络",
        "keywords": ["朋友", "家人", "同事", "伴侣", "认识"]
    },
    "skills": {
        "name": "技能知识",
        "description": "用户的技能、知识和专业领域",
        "keywords": ["擅长", "会", "技能", "专业", "学习"]
    },
    "goals": {
        "name": "目标计划",
        "description": "用户的目标、愿望和计划",
        "keywords": ["想要", "计划", "目标", "希望", "打算"]
    },
    "experiences": {
        "name": "经历体验",
        "description": "用户的过往经历和重要事件",
        "keywords": ["经历", "曾经", "去过", "做过", "体验"]
    }
}

# 记忆类型到分类的默认映射
TYPE_TO_CATEGORY_MAP = {
    MemoryType.PREFERENCE: "preferences",
    MemoryType.FACT: "personal_info",
    MemoryType.EXPERIENCE: "experiences",
    MemoryType.SKILL: "skills",
    MemoryType.OPINION: "preferences",
    MemoryType.RELATIONSHIP: "relationships",
    MemoryType.HABIT: "preferences",
    MemoryType.GOAL: "goals"
}


class MemoryCategory:
    """记忆分类"""
    
    def __init__(
        self, 
        id: str, 
        name: str, 
        description: str = "",
        is_system: bool = False
    ):
        self.id = id
        self.name = name
        self.description = description
        self.is_system = is_system # 是否为系统分类
        self.item_count = 0
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "is_system": self.is_system,
            "item_count": self.item_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryCategory":
        cat = cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            is_system=data.get("is_system", False)
        )
        cat.item_count = data.get("item_count", 0)
        if isinstance(data.get("created_at"), str):
            cat.created_at = datetime.fromisoformat(data["created_at"])
        if isinstance(data.get("updated_at"), str):
            cat.updated_at = datetime.fromisoformat(data["updated_at"])
        return cat


class CategoryManager:
    """
    分类管理器
    
    负责：
    1. 管理系统分类和自定义分类
    2. 自动为记忆项分配分类
    3. 统计各分类的记忆数量
    """
    
    def __init__(self, storage_dir: Path = None):
        if storage_dir is None:
            storage_dir = paths.MEMORY_DIR
        
        self.storage_path = storage_dir / "categories.json"
        self.categories: Dict[str, MemoryCategory] = {}
        
        self._init_system_categories()
        self._load()
    
    def _init_system_categories(self):
        """初始化系统分类"""
        for cat_id, cat_info in SYSTEM_CATEGORIES.items():
            self.categories[cat_id] = MemoryCategory(
                id=cat_id,
                name=cat_info["name"],
                description=cat_info["description"],
                is_system=True
            )
    
    def _load(self):
        """加载自定义分类"""
        if not self.storage_path.exists():
            return
        
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for cat_id, cat_data in data.get("categories", {}).items():
                if cat_id not in SYSTEM_CATEGORIES:
                    self.categories[cat_id] = MemoryCategory.from_dict(cat_data)
                else:
                    # 更新系统分类的统计信息
                    self.categories[cat_id].item_count = cat_data.get("item_count", 0)
            
            logger.info(f"已加载 {len(self.categories)} 个分类")
            
        except Exception as e:
            logger.error(f"加载分类失败: {e}")
    
    def _save(self):
        """保存分类"""
        try:
            data = {
                "categories": {
                    cid: cat.to_dict() for cid, cat in self.categories.items()
                },
                "updated_at": datetime.now().isoformat()
            }
            
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"保存分类失败: {e}")
    
    def auto_categorize(self, item: MemoryItem) -> str:
        """
        自动为记忆项分配分类
        
        策略：
        1. 优先使用记忆类型映射
        2. 其次进行关键词匹配
        3. 默认归类到 personal_info
        """
        # 策略1：类型映射
        if item.memory_type in TYPE_TO_CATEGORY_MAP:
            category_id = TYPE_TO_CATEGORY_MAP[item.memory_type]
            item.category = category_id
            self._increment_count(category_id)
            return category_id
        
        # 策略2：关键词匹配
        content_lower = item.content.lower()
        for cat_id, cat_info in SYSTEM_CATEGORIES.items():
            for keyword in cat_info.get("keywords", []):
                if keyword in content_lower:
                    item.category = cat_id
                    self._increment_count(cat_id)
                    return cat_id
        
        # 策略3：默认分类
        default_category = "personal_info"
        item.category = default_category
        self._increment_count(default_category)
        return default_category
    
    def _increment_count(self, category_id: str):
        """增加分类计数"""
        if category_id in self.categories:
            self.categories[category_id].item_count += 1
            self.categories[category_id].updated_at = datetime.now()
            self._save()
    
    def add_category(self, id: str, name: str, description: str = "") -> MemoryCategory:
        """添加自定义分类"""
        if id in self.categories:
            logger.warning(f"分类 {id} 已存在")
            return self.categories[id]
        
        category = MemoryCategory(
            id=id,
            name=name,
            description=description,
            is_system=False
        )
        self.categories[id] = category
        self._save()
        
        logger.info(f"已添加自定义分类: {name}")
        return category
    
    def get(self, category_id: str) -> Optional[MemoryCategory]:
        """获取分类"""
        return self.categories.get(category_id)
    
    def get_all(self) -> List[MemoryCategory]:
        """获取所有分类"""
        return list(self.categories.values())
    
    def get_system_categories(self) -> List[MemoryCategory]:
        """获取系统分类"""
        return [cat for cat in self.categories.values() if cat.is_system]
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取分类统计"""
        stats = {
            "total_categories": len(self.categories),
            "system_categories": len([c for c in self.categories.values() if c.is_system]),
            "custom_categories": len([c for c in self.categories.values() if not c.is_system]),
            "category_items": {
                cat.name: cat.item_count 
                for cat in self.categories.values()
            }
        }
        return stats
