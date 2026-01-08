"""
多层记忆存储系统

存储层次：
1. SessionSummaryStore - 会话总结存储（第一阶段输出）
2. MemoryItemStore - 结构化记忆项存储（第二阶段输出）
3. 两者共享向量索引用于检索
"""
import json
import os
import shutil
import asyncio
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import logging

from backend.config import paths
from .memory_item import MemoryItem, MemoryType, SessionSummary

logger = logging.getLogger(__name__)

class BaseMemoryStore:
    """
    基础存储类
    提供通用的持久化、加载和异步保存功能
    """
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.executor = ThreadPoolExecutor(max_workers=1)
        
        # 确保目录存在
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _save_json(self, data: Dict[str, Any]):
        """原子写入 JSON 文件"""
        try:
            tmp_path = f"{self.file_path}.tmp"
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            shutil.move(tmp_path, self.file_path)
            logger.debug(f"数据已保存到 {self.file_path}")
        except Exception as e:
            logger.error(f"保存失败: {e}")
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    
    def _load_json(self) -> Dict[str, Any]:
        """加载 JSON 文件"""
        if self.file_path.exists():
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载失败: {e}")
        return {}
    
    async def save_async(self):
        """异步保存"""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(self.executor, self._do_save)
    
    def _do_save(self):
        """子类实现具体保存逻辑"""
        raise NotImplementedError


class SessionSummaryStore(BaseMemoryStore):
    """
    会话总结存储
    
    存储每个 Session 结束时生成的总结
    这是第一阶段的输出，后续会被结构化处理
    """
    
    def __init__(self, storage_dir: Path = None):
        if storage_dir is None:
            storage_dir = paths.MEMORY_DIR
        
        # 保存 storage_dir 供外部访问
        self.storage_dir = storage_dir
        
        super().__init__(storage_dir / "session_summaries.json")
        
        self.summaries: Dict[str, SessionSummary] = {}
        self._load()
    
    def _load(self):
        """加载已有的会话总结"""
        data = self._load_json()
        for summary_id, summary_data in data.get("summaries", {}).items():
            try:
                self.summaries[summary_id] = SessionSummary.from_dict(summary_data)
            except Exception as e:
                logger.warning(f"加载会话总结 {summary_id} 失败: {e}")
        
        logger.info(f"已加载 {len(self.summaries)} 条会话总结")
    
    def _do_save(self):
        """保存所有会话总结"""
        data = {
            "summaries": {
                sid: s.to_dict() for sid, s in self.summaries.items()
            },
            "updated_at": datetime.now().isoformat()
        }
        self._save_json(data)
    
    def add(self, summary: SessionSummary):
        """添加会话总结"""
        self.summaries[summary.id] = summary
        
        # 异步保存
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.save_async())
        except RuntimeError:
            self._do_save()
        
        logger.info(f"已添加会话总结: {summary.id} (session: {summary.session_id})")
    
    def get_unstructured(self) -> List[SessionSummary]:
        """获取未进行结构化处理的总结"""
        return [s for s in self.summaries.values() if not s.is_structured]
    
    def get_recent(self, count: int = 10) -> List[SessionSummary]:
        """获取最近的总结"""
        sorted_summaries = sorted(
            self.summaries.values(),
            key=lambda s: s.created_at,
            reverse=True
        )
        return sorted_summaries[:count]
    
    def mark_structured(self, summary_id: str, extracted_item_ids: List[str]):
        """标记总结已被结构化处理"""
        if summary_id in self.summaries:
            self.summaries[summary_id].mark_structured(extracted_item_ids)
            
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.save_async())
            except RuntimeError:
                self._do_save()


class MemoryItemStore(BaseMemoryStore):
    """
    结构化记忆项存储
    
    存储从会话总结中提取的结构化记忆项
    支持向量检索
    """
    
    def __init__(
        self, 
        storage_dir: Path = None,
        embedding_func: Optional[Callable[[str], List[float]]] = None
    ):
        if storage_dir is None:
            storage_dir = paths.MEMORY_DIR
        
        # 保存 storage_dir 供外部访问
        self.storage_dir = storage_dir
        
        super().__init__(storage_dir / "memory_items.json")
        
        self.embedding_func = embedding_func
        self.items: Dict[str, MemoryItem] = {}
        self.embeddings: Optional[np.ndarray] = None
        self.item_id_to_idx: Dict[str, int] = {}  # ID 到向量索引的映射
        
        self._load()
    
    def _load(self):
        """加载记忆项和向量"""
        data = self._load_json()
        
        # 加载记忆项
        for item_id, item_data in data.get("items", {}).items():
            try:
                self.items[item_id] = MemoryItem.from_dict(item_data)
            except Exception as e:
                logger.warning(f"加载记忆项 {item_id} 失败: {e}")
        
        # 加载向量
        embeddings_list = data.get("embeddings", [])
        if embeddings_list:
            self.embeddings = np.array(embeddings_list, dtype=np.float32)
        
        # 加载索引映射
        self.item_id_to_idx = data.get("item_id_to_idx", {})
        
        logger.info(f"已加载 {len(self.items)} 条结构化记忆项")
    
    def _do_save(self):
        """保存所有数据"""
        data = {
            "items": {iid: item.to_dict() for iid, item in self.items.items()},
            "embeddings": self.embeddings.tolist() if self.embeddings is not None else [],
            "item_id_to_idx": self.item_id_to_idx,
            "updated_at": datetime.now().isoformat()
        }
        self._save_json(data)
    
    def add(self, item: MemoryItem) -> str:
        """
        添加记忆项
        
        Returns:
            记忆项ID
        """
        # 生成 embedding
        if self.embedding_func and item.embedding is None:
            try:
                item.embedding = self.embedding_func(item.to_search_text())
            except Exception as e:
                logger.error(f"生成 embedding 失败: {e}")
        
        # 存储记忆项
        self.items[item.id] = item
        
        # 更新向量索引
        if item.embedding:
            idx = len(self.item_id_to_idx)
            self.item_id_to_idx[item.id] = idx
            
            vector_np = np.array([item.embedding], dtype=np.float32)
            if self.embeddings is None:
                self.embeddings = vector_np
            else:
                self.embeddings = np.vstack([self.embeddings, vector_np])
        
        # 异步保存
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.save_async())
        except RuntimeError:
            self._do_save()
        
        logger.info(f"已添加记忆项: [{item.memory_type.value}] {item.content[:30]}...")
        return item.id
    
    def add_batch(self, items: List[MemoryItem]) -> List[str]:
        """批量添加记忆项"""
        ids = []
        for item in items:
            # 生成 embedding
            if self.embedding_func and item.embedding is None:
                try:
                    item.embedding = self.embedding_func(item.to_search_text())
                except Exception as e:
                    logger.error(f"生成 embedding 失败: {e}")
            
            # 存储
            self.items[item.id] = item
            ids.append(item.id)
            
            # 更新向量索引
            if item.embedding:
                idx = len(self.item_id_to_idx)
                self.item_id_to_idx[item.id] = idx
                
                vector_np = np.array([item.embedding], dtype=np.float32)
                if self.embeddings is None:
                    self.embeddings = vector_np
                else:
                    self.embeddings = np.vstack([self.embeddings, vector_np])
        
        # 保存
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.save_async())
        except RuntimeError:
            self._do_save()
        
        logger.info(f"批量添加了 {len(ids)} 条记忆项")
        return ids
    
    def get(self, item_id: str) -> Optional[MemoryItem]:
        """获取记忆项"""
        item = self.items.get(item_id)
        if item:
            item.mark_accessed()
        return item
    
    def get_by_category(self, category: str) -> List[MemoryItem]:
        """按分类获取记忆项"""
        return [item for item in self.items.values() if item.category == category]
    
    def get_by_type(self, memory_type: MemoryType) -> List[MemoryItem]:
        """按类型获取记忆项"""
        return [item for item in self.items.values() if item.memory_type == memory_type]
    
    def search(
        self, 
        query: str, 
        top_k: int = 5, 
        threshold: float = 0.6,
        memory_type: Optional[MemoryType] = None,
        category: Optional[str] = None
    ) -> List[MemoryItem]:
        """
        向量检索记忆项
        
        Args:
            query: 查询文本
            top_k: 返回数量
            threshold: 相似度阈值
            memory_type: 过滤记忆类型
            category: 过滤分类
        
        Returns:
            匹配的记忆项列表（按相似度排序）
        """
        if not self.embedding_func or self.embeddings is None or len(self.items) == 0:
            return []
        
        try:
            # 生成查询向量
            query_vector = np.array(self.embedding_func(query), dtype=np.float32)
            
            # 计算余弦相似度
            norm_docs = np.linalg.norm(self.embeddings, axis=1)
            norm_query = np.linalg.norm(query_vector)
            
            if norm_query == 0:
                return []
            
            norm_docs[norm_docs == 0] = 1e-10
            similarities = np.dot(self.embeddings, query_vector) / (norm_docs * norm_query)
            
            # 构建 ID 到相似度的映射
            idx_to_id = {v: k for k, v in self.item_id_to_idx.items()}
            
            # 筛选和排序
            results = []
            for idx, score in enumerate(similarities):
                if score < threshold:
                    continue
                
                item_id = idx_to_id.get(idx)
                if not item_id or item_id not in self.items:
                    continue
                
                item = self.items[item_id]
                
                # 类型过滤
                if memory_type and item.memory_type != memory_type:
                    continue
                
                # 分类过滤
                if category and item.category != category:
                    continue
                
                results.append((item, float(score)))
            
            # 按相似度排序
            results.sort(key=lambda x: x[1], reverse=True)
            
            # 标记访问并返回
            top_items = []
            for item, score in results[:top_k]:
                item.mark_accessed()
                top_items.append(item)
            
            return top_items
            
        except Exception as e:
            logger.error(f"检索失败: {e}")
            return []
    
    def update_relations(self, item_id: str, related_ids: List[str]):
        """更新记忆项的关联关系"""
        if item_id in self.items:
            for rid in related_ids:
                self.items[item_id].add_related(rid)
            
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.save_async())
            except RuntimeError:
                self._do_save()
    
    def get_all_categories(self) -> List[str]:
        """获取所有分类"""
        categories = set()
        for item in self.items.values():
            if item.category:
                categories.add(item.category)
        return list(categories)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        type_counts = {}
        category_counts = {}
        
        for item in self.items.values():
            # 按类型统计
            t = item.memory_type.value
            type_counts[t] = type_counts.get(t, 0) + 1
            
            # 按分类统计
            if item.category:
                category_counts[item.category] = category_counts.get(item.category, 0) + 1
        
        return {
            "total_items": len(self.items),
            "type_distribution": type_counts,
            "category_distribution": category_counts,
            "has_embeddings": self.embeddings is not None,
            "embedding_count": len(self.item_id_to_idx)
        }
