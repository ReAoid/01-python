"""
搜索 Agent - 封装 SerpApi 搜索功能
"""

import os
import json
from typing import Dict, Any
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class SearchAgent:
    """基于 SerpApi 的网页搜索 Agent"""

    def __init__(self):
        """初始化搜索 Agent"""
        self.api_key = os.getenv("SERPAPI_API_KEY")
        if not self.api_key:
            print("⚠️  警告: SERPAPI_API_KEY 未配置,搜索功能可能无法使用")

    def _search_serpapi(self, query: str) -> str:
        """
        使用 SerpApi 执行搜索
        
        Args:
            query: 搜索查询词
            
        Returns:
            搜索结果文本
        """
        try:
            from serpapi import SerpApiClient
        except ImportError:
            return "错误: 未安装 serpapi 库,请运行: pip install google-search-results"

        if not self.api_key:
            return "错误: SERPAPI_API_KEY 未在环境变量中配置"

        print(f"🔍 正在执行 [SerpApi] 网页搜索: {query}")

        try:
            params = {
                "engine": "google",
                "q": query,
                "api_key": self.api_key,
                "gl": "cn",  # 国家代码
                "hl": "zh-cn",  # 语言代码
            }

            client = SerpApiClient(params)
            results = client.get_dict()

            # 智能解析: 优先寻找最直接的答案
            if "answer_box_list" in results:
                return "\n".join(results["answer_box_list"])

            if "answer_box" in results and "answer" in results["answer_box"]:
                return results["answer_box"]["answer"]

            if "knowledge_graph" in results and "description" in results["knowledge_graph"]:
                return results["knowledge_graph"]["description"]

            if "organic_results" in results and results["organic_results"]:
                # 返回前三个有机结果的摘要
                snippets = [
                    f"[{i + 1}] {res.get('title', '')}\n{res.get('snippet', '')}"
                    for i, res in enumerate(results["organic_results"][:3])
                ]
                return "\n\n".join(snippets)

            return f"对不起,没有找到关于 '{query}' 的信息。"

        except Exception as e:
            return f"搜索时发生错误: {str(e)}"

    def handle_handoff(self, task: Dict[str, Any]) -> str:
        """
        标准 MCP 入口方法 (异步兼容)
        
        Args:
            task: 任务参数字典,必须包含 'query' 字段
            
        Returns:
            JSON 格式的搜索结果
        """
        try:
            query = task.get("query")

            if not query:
                return json.dumps({
                    "status": "error",
                    "error": "缺少必需参数: query"
                }, ensure_ascii=False)

            # 执行搜索
            result = self._search_serpapi(query)

            return json.dumps({
                "status": "success",
                "query": query,
                "result": result
            }, ensure_ascii=False)

        except Exception as e:
            return json.dumps({
                "status": "error",
                "error": str(e)
            }, ensure_ascii=False)

    def run(self, query: str) -> str:
        """
        备用入口方法 (直接参数调用)
        
        Args:
            query: 搜索查询词
            
        Returns:
            搜索结果文本
        """
        return self._search_serpapi(query)


# 用于测试
if __name__ == "__main__":
    agent = SearchAgent()
    test_query = "2025年英伟达最新的GPU型号是什么"
    print("\n=== 测试搜索功能 ===")
    result = agent.handle_handoff({"query": test_query})
    print(f"\n结果:\n{result}")
