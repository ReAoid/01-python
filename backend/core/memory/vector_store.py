import json
import os
import numpy as np
from typing import List, Dict, Any, Callable, Optional
from loguru import logger

class VectorStore:
    """
    轻量级向量存储实现。
    使用 JSON 文件存储文本和元数据，使用 numpy 计算余弦相似度。

    TODO: [性能优化]
    1. 后端替换：支持更强大的向量数据库后端 (如 ChromaDB, FAISS, Qdrant) 以提高大规模数据的检索性能和持久化能力。
    2. 异步支持：实现异步 I/O 操作 (save/load) 以及异步检索，避免阻塞主线程。
    3. 索引优化：对于大规模数据，添加索引机制 (如 HNSW) 以加速检索。
    """

    def __init__(self, file_path: str = "memory_store.json", embedding_func: Optional[Callable[[str], List[float]]] = None):
        """
        初始化向量存储。

        Args:
            file_path: 存储数据的文件路径
            embedding_func: 用于生成文本向量的函数，接收字符串返回浮点数列表
        """
        self.file_path = file_path
        self.embedding_func = embedding_func
        self.documents: List[Dict[str, Any]] = []
        self.embeddings: Optional[np.ndarray] = None
        
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
        """保存数据到文件"""
        try:
            data = {
                "documents": self.documents,
                "embeddings": self.embeddings.tolist() if self.embeddings is not None else []
            }
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("记忆数据已保存")
        except Exception as e:
            logger.error(f"保存记忆文件失败: {e}")

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
            
            doc = {
                "text": text,
                "metadata": metadata or {},
                "id": len(self.documents)
            }
            
            self.documents.append(doc)
            
            vector_np = np.array([vector], dtype=np.float32)
            if self.embeddings is None:
                self.embeddings = vector_np
            else:
                self.embeddings = np.vstack([self.embeddings, vector_np])
                
            self.save()
            logger.info(f"已添加记忆: {text[:20]}...")
            
        except Exception as e:
            logger.error(f"添加记忆失败: {e}")

    def search(self, query: str, top_k: int = 3, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """
        搜索相似文本。

        TODO: [功能增强]
        1. 元数据过滤：添加 metadata filtering 功能，允许按时间、来源等条件过滤记忆。
        2. 混合检索：支持关键词 (BM25) + 向量的混合检索模式，提高对专有名词的命中率。

        Args:
            query: 查询文本
            top_k: 返回结果数量
            threshold: 相似度阈值

        Returns:
            相似文档列表
        """
        if not self.embedding_func:
            raise ValueError("未设置 embedding_func")
            
        if self.embeddings is None or len(self.documents) == 0:
            return []

        try:
            query_vector = np.array(self.embedding_func(query), dtype=np.float32)
            
            # 计算余弦相似度
            # norm_docs = np.linalg.norm(self.embeddings, axis=1)
            # norm_query = np.linalg.norm(query_vector)
            # similarities = np.dot(self.embeddings, query_vector) / (norm_docs * norm_query)
            
            # 假设 embedding_func 返回的向量已经是归一化的（OpenAI embeddings 通常是归一化的）
            # 如果不是，需要先归一化。这里为了保险起见，手动计算
            norm_docs = np.linalg.norm(self.embeddings, axis=1)
            norm_query = np.linalg.norm(query_vector)
            
            # 避免除以零
            if norm_query == 0:
                return []
            norm_docs[norm_docs == 0] = 1e-10
            
            similarities = np.dot(self.embeddings, query_vector) / (norm_docs * norm_query)
            
            # 获取 top_k 索引
            top_indices = np.argsort(similarities)[::-1][:top_k]
            
            results = []
            for idx in top_indices:
                score = float(similarities[idx])
                if score >= threshold:
                    doc = self.documents[idx].copy()
                    doc["score"] = score
                    results.append(doc)
            
            return results
            
        except Exception as e:
            logger.error(f"搜索记忆失败: {e}")
            return []

