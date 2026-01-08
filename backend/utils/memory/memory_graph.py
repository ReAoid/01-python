"""
记忆图谱
实现 Memory Graph Connection

功能：
1. 建立记忆项之间的关联关系
2. 支持关联发现和上下文扩展
3. 提供图遍历和关系查询
"""
from typing import List, Dict, Set, Optional, Tuple, Any
from datetime import datetime
from pathlib import Path
import json
from collections import defaultdict
import logging

from backend.config import paths
from .memory_item import MemoryItem

logger = logging.getLogger(__name__)

class RelationType:
    """关系类型"""
    TEMPORAL = "temporal"           # 时间相邻
    SEMANTIC = "semantic"           # 语义相似
    CATEGORY = "category"           # 同分类
    REFERENCED = "referenced"       # 引用关系
    CONTRADICTS = "contradicts"     # 矛盾关系
    UPDATES = "updates"             # 更新关系


class MemoryEdge:
    """记忆关联边"""
    
    def __init__(
        self, 
        source_id: str, 
        target_id: str, 
        relation_type: str,
        weight: float = 1.0
    ):
        self.source_id = source_id
        self.target_id = target_id
        self.relation_type = relation_type
        self.weight = weight
        self.created_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type,
            "weight": self.weight,
            "created_at": self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEdge":
        edge = cls(
            source_id=data["source_id"],
            target_id=data["target_id"],
            relation_type=data["relation_type"],
            weight=data.get("weight", 1.0)
        )
        if isinstance(data.get("created_at"), str):
            edge.created_at = datetime.fromisoformat(data["created_at"])
        return edge


class MemoryGraph:
    """
    记忆图谱
    
    使用邻接表表示有向图，支持：
    - 添加/删除节点和边
    - 关联发现（BFS/DFS）
    - 路径查找
    - 子图提取
    """
    
    def __init__(self, storage_dir: Path = None):
        if storage_dir is None:
            storage_dir = paths.MEMORY_DIR
        
        self.storage_path = storage_dir / "memory_graph.json"
        
        # 邻接表：item_id -> List[MemoryEdge]
        self.adjacency: Dict[str, List[MemoryEdge]] = defaultdict(list)
        
        # 反向邻接表：item_id -> List[MemoryEdge]（用于快速查找入边）
        self.reverse_adjacency: Dict[str, List[MemoryEdge]] = defaultdict(list)
        
        # 节点集合
        self.nodes: Set[str] = set()
        
        self._load()
    
    def _load(self):
        """加载图谱"""
        if not self.storage_path.exists():
            return
        
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.nodes = set(data.get("nodes", []))
            
            for edge_data in data.get("edges", []):
                edge = MemoryEdge.from_dict(edge_data)
                self.adjacency[edge.source_id].append(edge)
                self.reverse_adjacency[edge.target_id].append(edge)
            
            logger.info(f"已加载记忆图谱: {len(self.nodes)} 节点, {self._edge_count()} 边")
            
        except Exception as e:
            logger.error(f"加载图谱失败: {e}")
    
    def _save(self):
        """保存图谱"""
        try:
            edges = []
            for edge_list in self.adjacency.values():
                for edge in edge_list:
                    edges.append(edge.to_dict())
            
            data = {
                "nodes": list(self.nodes),
                "edges": edges,
                "updated_at": datetime.now().isoformat()
            }
            
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"保存图谱失败: {e}")
    
    def _edge_count(self) -> int:
        """统计边数量"""
        return sum(len(edges) for edges in self.adjacency.values())
    
    def add_node(self, item_id: str):
        """添加节点"""
        self.nodes.add(item_id)
    
    def add_edge(
        self, 
        source_id: str, 
        target_id: str, 
        relation_type: str = RelationType.SEMANTIC,
        weight: float = 1.0
    ):
        """添加边"""
        # 确保节点存在
        self.nodes.add(source_id)
        self.nodes.add(target_id)
        
        # 检查是否已存在
        for edge in self.adjacency[source_id]:
            if edge.target_id == target_id and edge.relation_type == relation_type:
                # 更新权重
                edge.weight = max(edge.weight, weight)
                return
        
        # 添加新边
        edge = MemoryEdge(source_id, target_id, relation_type, weight)
        self.adjacency[source_id].append(edge)
        self.reverse_adjacency[target_id].append(edge)
        
        self._save()
    
    def add_bidirectional_edge(
        self, 
        item1_id: str, 
        item2_id: str, 
        relation_type: str = RelationType.SEMANTIC,
        weight: float = 1.0
    ):
        """添加双向边"""
        self.add_edge(item1_id, item2_id, relation_type, weight)
        self.add_edge(item2_id, item1_id, relation_type, weight)
    
    def get_neighbors(
        self, 
        item_id: str, 
        relation_type: Optional[str] = None
    ) -> List[Tuple[str, MemoryEdge]]:
        """
        获取邻居节点
        
        Returns:
            List of (neighbor_id, edge)
        """
        result = []
        for edge in self.adjacency.get(item_id, []):
            if relation_type is None or edge.relation_type == relation_type:
                result.append((edge.target_id, edge))
        return result
    
    def get_incoming(
        self, 
        item_id: str, 
        relation_type: Optional[str] = None
    ) -> List[Tuple[str, MemoryEdge]]:
        """获取入边邻居"""
        result = []
        for edge in self.reverse_adjacency.get(item_id, []):
            if relation_type is None or edge.relation_type == relation_type:
                result.append((edge.source_id, edge))
        return result
    
    def find_related(
        self, 
        item_id: str, 
        max_depth: int = 2,
        max_results: int = 10
    ) -> List[Tuple[str, int, float]]:
        """
        查找相关记忆（BFS）
        
        Args:
            item_id: 起始节点
            max_depth: 最大搜索深度
            max_results: 最大结果数
        
        Returns:
            List of (item_id, depth, total_weight)
        """
        if item_id not in self.nodes:
            return []
        
        visited = {item_id}
        results = []
        queue = [(item_id, 0, 1.0)]  # (node, depth, accumulated_weight)
        
        while queue and len(results) < max_results:
            current_id, depth, acc_weight = queue.pop(0)
            
            if depth >= max_depth:
                continue
            
            for neighbor_id, edge in self.get_neighbors(current_id):
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    new_weight = acc_weight * edge.weight
                    results.append((neighbor_id, depth + 1, new_weight))
                    queue.append((neighbor_id, depth + 1, new_weight))
        
        # 按权重排序
        results.sort(key=lambda x: x[2], reverse=True)
        return results[:max_results]
    
    def find_path(
        self, 
        source_id: str, 
        target_id: str, 
        max_depth: int = 5
    ) -> Optional[List[str]]:
        """
        查找两个记忆之间的路径
        
        Returns:
            路径上的节点列表，如果不存在则返回 None
        """
        if source_id not in self.nodes or target_id not in self.nodes:
            return None
        
        visited = {source_id}
        queue = [(source_id, [source_id])]
        
        while queue:
            current_id, path = queue.pop(0)
            
            if current_id == target_id:
                return path
            
            if len(path) >= max_depth:
                continue
            
            for neighbor_id, _ in self.get_neighbors(current_id):
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    queue.append((neighbor_id, path + [neighbor_id]))
        
        return None
    
    def get_cluster(self, item_id: str, max_size: int = 20) -> Set[str]:
        """
        获取包含指定节点的连通分量（子图）
        
        Returns:
            子图中的所有节点ID
        """
        if item_id not in self.nodes:
            return set()
        
        cluster = set()
        queue = [item_id]
        
        while queue and len(cluster) < max_size:
            current_id = queue.pop(0)
            if current_id in cluster:
                continue
            
            cluster.add(current_id)
            
            # 添加所有邻居
            for neighbor_id, _ in self.get_neighbors(current_id):
                if neighbor_id not in cluster:
                    queue.append(neighbor_id)
            
            for neighbor_id, _ in self.get_incoming(current_id):
                if neighbor_id not in cluster:
                    queue.append(neighbor_id)
        
        return cluster
    
    def link_by_similarity(
        self, 
        item1: MemoryItem, 
        item2: MemoryItem, 
        similarity: float
    ):
        """
        基于相似度建立关联
        
        Args:
            item1, item2: 两个记忆项
            similarity: 相似度分数 (0-1)
        """
        if similarity > 0.8:
            # 高相似度：强关联
            self.add_bidirectional_edge(
                item1.id, item2.id, 
                RelationType.SEMANTIC, 
                weight=similarity
            )
        elif similarity > 0.6:
            # 中等相似度：弱关联
            self.add_bidirectional_edge(
                item1.id, item2.id, 
                RelationType.SEMANTIC, 
                weight=similarity * 0.7
            )
    
    def link_by_category(self, item1: MemoryItem, item2: MemoryItem):
        """基于分类建立关联"""
        if item1.category and item1.category == item2.category:
            self.add_bidirectional_edge(
                item1.id, item2.id,
                RelationType.CATEGORY,
                weight=0.5
            )
    
    def link_temporal(self, items: List[MemoryItem]):
        """建立时间相邻关联（按创建时间排序后相邻的记忆）"""
        if len(items) < 2:
            return
        
        sorted_items = sorted(items, key=lambda x: x.created_at)
        
        for i in range(len(sorted_items) - 1):
            self.add_edge(
                sorted_items[i].id,
                sorted_items[i + 1].id,
                RelationType.TEMPORAL,
                weight=0.3
            )
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取图谱统计"""
        relation_counts = defaultdict(int)
        for edge_list in self.adjacency.values():
            for edge in edge_list:
                relation_counts[edge.relation_type] += 1
        
        return {
            "node_count": len(self.nodes),
            "edge_count": self._edge_count(),
            "relation_distribution": dict(relation_counts),
            "avg_degree": self._edge_count() / max(len(self.nodes), 1)
        }
