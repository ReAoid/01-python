import json
import os
import numpy as np
import time
import asyncio
import shutil
from typing import List, Dict, Any, Callable, Optional
import logging
from concurrent.futures import ThreadPoolExecutor

from backend.config import migration

logger = logging.getLogger(__name__)

class VectorStore:
    """
    轻量级向量存储实现。
    使用 JSON 文件存储文本和元数据，使用 numpy 计算余弦相似度。
    
    [优化功能]
    - 原子写入 (Atomic Write)
    - 异步保存 (Async Save)
    - 自动时间戳
    """

    def __init__(self, file_path: str = None, embedding_func: Optional[Callable[[str], List[float]]] = None):
        """
        初始化向量存储。

        Args:
            file_path: 存储数据的文件路径
            embedding_func: 用于生成文本向量的函数，接收字符串返回浮点数列表
        """
        if file_path is None:
            file_path = str(migration.user_memory_dir / "memory_store.json")
            
            # 确保存储目录存在
            store_dir = os.path.dirname(file_path)
            if store_dir and not os.path.exists(store_dir):
                os.makedirs(store_dir)

        self.file_path = file_path
        self.embedding_func = embedding_func
        self.documents: List[Dict[str, Any]] = []
        self.embeddings: Optional[np.ndarray] = None
        
        # 线程池用于执行阻塞的 I/O 操作
        self.executor = ThreadPoolExecutor(max_workers=1)
        
        self.load()

    def load(self):
        """从文件加载数据"""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.documents = data.get("documents", [])
                    embeddings_list = data.get("embeddings", [])
                    if embeddings_list:
                        self.embeddings = np.array(embeddings_list, dtype=np.float32)
                    else:
                        self.embeddings = None
                logger.info(f"已加载 {len(self.documents)} 条记忆数据")
            except Exception as e:
                logger.error(f"加载记忆文件失败: {e}")
                self.documents = []
                self.embeddings = None
        else:
            logger.info("未找到记忆文件，将创建新的存储")

    def save(self):
        """同步保存数据到文件 (不推荐直接调用，尽量使用 save_async)"""
        try:
            data = {
                "documents": self.documents,
                "embeddings": self.embeddings.tolist() if self.embeddings is not None else []
            }
            
            # 原子写入策略：先写临时文件，再重命名
            tmp_path = f"{self.file_path}.tmp"
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            # 重命名覆盖 (原子操作)
            shutil.move(tmp_path, self.file_path)
            
            logger.info("记忆数据已保存 (原子写入)")
        except Exception as e:
            logger.error(f"保存记忆文件失败: {e}")
            # 尝试清理临时文件
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except:
                    pass

    async def save_async(self):
        """异步保存数据到文件"""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(self.executor, self.save)

    def add(self, text: str, metadata: Dict[str, Any] = None):
        """
        添加一条文本记录。

        Args:
            text: 文本内容
            metadata: 元数据字典
        """
        if not self.embedding_func:
            raise ValueError("未设置 embedding_func，无法生成向量")

        try:
            vector = self.embedding_func(text)
            
            # 注入时间戳
            meta = metadata or {}
            if "timestamp" not in meta:
                meta["timestamp"] = time.time()

            doc = {
                "text": text,
                "metadata": meta,
                "id": len(self.documents)
            }
            
            self.documents.append(doc)
            
            vector_np = np.array([vector], dtype=np.float32)
            if self.embeddings is None:
                self.embeddings = vector_np
            else:
                self.embeddings = np.vstack([self.embeddings, vector_np])
                
            # 使用异步保存
            # 注意: add 本身是同步方法，这里我们创建一个 Task 来执行异步保存，不阻塞当前流程
            # 如果是在异步上下文中调用，最好将 add 也改为 async add
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.save_async())
            except RuntimeError:
                # 如果没有运行中的循环 (例如脚本模式)，回退到同步保存
                self.save()
            
            logger.info(f"已添加记忆: {text[:20]}...")
            
        except Exception as e:
            logger.error(f"添加记忆失败: {e}")

    def search(self, query: str, top_k: int = 3, threshold: float = 0.7, time_decay: bool = True) -> List[Dict[str, Any]]:
        """
        搜索相似文本。

        功能:
        1. 向量相似度检索 (Semantic Search)
        2. 时间衰减 (Time Decay): 较新的记忆得分更高
        3. 关键词加权 (Keyword Boosting): 包含查询词的记忆得分更高

        Args:
            query: 查询文本
            top_k: 返回结果数量
            threshold: 相似度阈值
            time_decay: 是否启用时间衰减

        Returns:
            相似文档列表
        """
        if not self.embedding_func:
            raise ValueError("未设置 embedding_func")
            
        if self.embeddings is None or len(self.documents) == 0:
            return []

        try:
            query_vector = np.array(self.embedding_func(query), dtype=np.float32)
            
            # 1. 计算基础向量相似度
            norm_docs = np.linalg.norm(self.embeddings, axis=1)
            norm_query = np.linalg.norm(query_vector)
            
            if norm_query == 0:
                return []
            norm_docs[norm_docs == 0] = 1e-10
            
            similarities = np.dot(self.embeddings, query_vector) / (norm_docs * norm_query)
            
            # 2. 应用加权逻辑
            current_time = time.time()
            query_tokens = set(query.lower().split()) # 简单分词用于关键词匹配

            final_scores = []
            for idx, base_score in enumerate(similarities):
                score = base_score
                doc = self.documents[idx]
                
                # A. 关键词加权 (Keyword Boosting)
                # 简单的逻辑：如果 query 中的词在 doc 文本中出现，微量加分
                # 这有助于捞回那些向量相似度不高但包含精准关键词的条目
                text_lower = doc['text'].lower()
                matches = sum(1 for token in query_tokens if token in text_lower)
                if matches > 0:
                    score += matches * 0.05  # 每个匹配词 +0.05 分
                
                # B. 时间衰减 (Time Decay)
                if time_decay:
                    timestamp = doc.get("metadata", {}).get("timestamp", 0)
                    if timestamp > 0:
                        # 计算天数差
                        days_diff = (current_time - timestamp) / (86400.0)
                        # 衰减公式: score * (1 / (1 + decay_rate * days_diff))
                        # decay_rate = 0.01 意味着 100 天前的记忆权重减半
                        decay_factor = 1.0 / (1.0 + 0.01 * days_diff)
                        score *= decay_factor
                
                final_scores.append(score)
            
            final_scores = np.array(final_scores)

            # 3. 排序并取 Top-K
            top_indices = np.argsort(final_scores)[::-1][:top_k]
            
            results = []
            for idx in top_indices:
                score = float(final_scores[idx])
                if score >= threshold:
                    doc = self.documents[idx].copy()
                    doc["score"] = score
                    results.append(doc)
            
            return results
            
        except Exception as e:
            logger.error(f"搜索记忆失败: {e}")
            return []

