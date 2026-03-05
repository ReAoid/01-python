"""
记忆系统模块测试文件

测试记忆系统各项功能（清晰分阶段测试）:

阶段 1: 短期记忆测试 (ShortTermMemory)
阶段 2: 会话总结存储测试 (SessionSummaryStore)
阶段 3: 记忆项存储测试 (MemoryItemStore)
阶段 4: 分类管理器测试 (CategoryManager)
阶段 5: 记忆图谱测试 (MemoryGraph)
阶段 6: 记忆管理器集成测试 (MemoryManager)

使用方法：
    cd /Users/mingy/Documents/python/01-python
    python backend/test/test_memory.py

前置条件：
    - 配置有效的 LLM API（用于生成总结和 embedding）
"""

import asyncio
import sys
import logging
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from backend.config import paths

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# 路径配置
# -----------------------------------------------------------------------------
ROOT_DIR = paths.get_root_dir()

# 确保 backend 模块可以被导入
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

try:
    from backend.core.message import Message
    from backend.utils.memory import (
        ShortTermMemory,
        SessionSummary,
        SessionSummaryStore,
        MemoryItem,
        MemoryType,
        MemoryItemStore,
        CategoryManager,
        MemoryGraph,
        RelationType,
        MemoryManager,
        MemoryStructurer
    )
    from backend.utils.llm.openai_llm import OpenaiLlm
    from backend.config import settings
except ImportError as e:
    print(f"❌ 无法导入必要模块: {e}")
    print("请检查项目路径配置")
    sys.exit(1)


class MemoryTester:
    """记忆系统测试类 - 分阶段测试记忆系统功能"""
    
    def __init__(self):
        self.temp_dir = None
        self.llm = None
        self.test_results = []
    
    def setup(self):
        """测试前准备"""
        # 创建临时测试目录
        self.temp_dir = tempfile.mkdtemp(prefix="memory_test_")
        logger.info(f"创建临时测试目录: {self.temp_dir}")
        
        # 初始化 LLM（用于需要 LLM 的测试）
        try:
            self.llm = OpenaiLlm()
            logger.info("LLM 初始化成功")
        except Exception as e:
            logger.warning(f"LLM 初始化失败: {e}，部分测试将被跳过")
            self.llm = None
    
    def cleanup(self):
        """测试后清理"""
        if self.temp_dir and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
            logger.info(f"清理临时测试目录: {self.temp_dir}")
    
    async def test_short_term_memory(self) -> bool:
        """
        阶段 1: 短期记忆测试
        
        测试内容：
        - 添加消息
        - 滑动窗口机制
        - 获取上下文
        - 清空记忆
        """
        print("\n" + "="*60)
        print("阶段 1: 短期记忆测试 (ShortTermMemory)")
        print("="*60)
        
        try:
            # 创建短期记忆实例
            stm = ShortTermMemory(max_messages=5)
            
            # 测试 1.1: 添加消息
            print("\n[1.1] 添加消息...")
            stm.add("user", "你好")
            stm.add("assistant", "你好！有什么可以帮助你的吗？")
            stm.add("user", "今天天气怎么样？")
            stm.add("assistant", "抱歉，我无法获取实时天气信息。")
            
            messages = stm.get_messages()
            assert len(messages) == 4, f"消息数量错误: 期望 4，实际 {len(messages)}"
            print(f"✅ 添加 4 条消息成功")
            
            # 测试 1.2: 滑动窗口机制
            print("\n[1.2] 测试滑动窗口...")
            stm.add("user", "给我讲个笑话")
            stm.add("assistant", "好的，让我想想...")
            stm.add("user", "快点")
            
            messages = stm.get_messages()
            assert len(messages) == 5, f"滑动窗口失败: 期望 5，实际 {len(messages)}"
            print(f"✅ 滑动窗口机制正常，保持 5 条消息")
            
            # 测试 1.3: 获取上下文
            print("\n[1.3] 获取上下文文本...")
            context = stm.get_context_text()
            assert "user:" in context and "assistant:" in context
            print(f"✅ 上下文文本获取成功 ({len(context)} 字符)")
            
            # 测试 1.4: 清空记忆
            print("\n[1.4] 清空记忆...")
            stm.clear()
            assert len(stm.get_messages()) == 0
            print("✅ 记忆清空成功")
            
            print("\n✅ 阶段 1 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 1 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_session_summary_store(self) -> bool:
        """
        阶段 2: 会话总结存储测试
        
        测试内容：
        - 添加会话总结
        - 检索总结
        - 获取所有总结
        - 持久化和加载
        """
        print("\n" + "="*60)
        print("阶段 2: 会话总结存储测试 (SessionSummaryStore)")
        print("="*60)
        
        try:
            # 创建会话总结存储实例
            store = SessionSummaryStore(storage_dir=self.temp_dir)
            
            # 测试 2.1: 添加会话总结
            print("\n[2.1] 添加会话总结...")
            summary1 = SessionSummary(
                session_id="test_session_1",
                summary="用户询问天气情况，助手无法提供实时天气。",
                key_points=["天气查询", "实时信息限制"],
                topics=["天气"],
                sentiment="neutral",
                user_info={},
                timestamp=datetime.now()
            )
            
            store.add_summary(summary1)
            assert len(store.summaries) == 1
            print(f"✅ 添加总结成功 (session_id: {summary1.session_id})")
            
            # 测试 2.2: 检索总结
            print("\n[2.2] 检索总结...")
            retrieved = store.get_summary("test_session_1")
            assert retrieved is not None
            assert retrieved.session_id == "test_session_1"
            print(f"✅ 检索总结成功: {retrieved.summary[:50]}...")
            
            # 测试 2.3: 添加多个总结
            print("\n[2.3] 添加多个总结...")
            summary2 = SessionSummary(
                session_id="test_session_2",
                summary="用户请求讲笑话，助手准备提供内容。",
                key_points=["娱乐请求"],
                topics=["笑话"],
                sentiment="positive",
                user_info={},
                timestamp=datetime.now()
            )
            store.add_summary(summary2)
            
            all_summaries = store.get_all_summaries()
            assert len(all_summaries) == 2
            print(f"✅ 存储中有 {len(all_summaries)} 个总结")
            
            # 测试 2.4: 持久化
            print("\n[2.4] 测试持久化...")
            store.save()
            
            # 创建新实例并加载
            store2 = SessionSummaryStore(storage_dir=self.temp_dir)
            assert len(store2.summaries) == 2
            print("✅ 持久化和加载成功")
            
            print("\n✅ 阶段 2 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 2 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_memory_item_store(self) -> bool:
        """
        阶段 3: 记忆项存储测试
        
        测试内容：
        - 添加记忆项
        - 检索记忆项
        - 相似度搜索（如果有 embedding）
        - 持久化
        """
        print("\n" + "="*60)
        print("阶段 3: 记忆项存储测试 (MemoryItemStore)")
        print("="*60)
        
        try:
            # 创建记忆项存储实例（不使用 embedding 以简化测试）
            store = MemoryItemStore(
                storage_dir=self.temp_dir,
                embedding_func=None  # 不使用 embedding
            )
            
            # 测试 3.1: 添加记忆项
            print("\n[3.1] 添加记忆项...")
            item1 = MemoryItem(
                content="用户喜欢晴天",
                memory_type=MemoryType.PREFERENCE,
                importance=0.7,
                confidence=0.9,
                tags=["天气", "偏好"]
            )
            
            store.add_item(item1)
            assert len(store.items) == 1
            print(f"✅ 添加记忆项成功 (id: {item1.id[:8]}...)")
            
            # 测试 3.2: 检索记忆项
            print("\n[3.2] 检索记忆项...")
            retrieved = store.get_item(item1.id)
            assert retrieved is not None
            assert retrieved.content == "用户喜欢晴天"
            print(f"✅ 检索成功: {retrieved.content}")
            
            # 测试 3.3: 添加多个记忆项
            print("\n[3.3] 添加多个记忆项...")
            item2 = MemoryItem(
                content="用户讨厌下雨天",
                memory_type=MemoryType.PREFERENCE,
                importance=0.6,
                tags=["天气", "偏好"]
            )
            item3 = MemoryItem(
                content="用户在北京工作",
                memory_type=MemoryType.FACT,
                importance=0.8,
                tags=["工作", "地点"]
            )
            
            store.add_item(item2)
            store.add_item(item3)
            
            all_items = store.get_all_items()
            assert len(all_items) == 3
            print(f"✅ 存储中有 {len(all_items)} 个记忆项")
            
            # 测试 3.4: 按类型筛选
            print("\n[3.4] 按类型筛选...")
            preferences = [item for item in all_items if item.memory_type == MemoryType.PREFERENCE]
            assert len(preferences) == 2
            print(f"✅ 找到 {len(preferences)} 个偏好类记忆")
            
            # 测试 3.5: 持久化
            print("\n[3.5] 测试持久化...")
            store.save()
            
            # 创建新实例并加载
            store2 = MemoryItemStore(storage_dir=self.temp_dir, embedding_func=None)
            assert len(store2.items) == 3
            print("✅ 持久化和加载成功")
            
            print("\n✅ 阶段 3 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 3 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_category_manager(self) -> bool:
        """
        阶段 4: 分类管理器测试
        
        测试内容：
        - 创建分类
        - 添加记忆到分类
        - 检索分类
        - 持久化
        """
        print("\n" + "="*60)
        print("阶段 4: 分类管理器测试 (CategoryManager)")
        print("="*60)
        
        try:
            # 创建分类管理器实例
            manager = CategoryManager(storage_dir=self.temp_dir)
            
            # 测试 4.1: 创建分类
            print("\n[4.1] 创建分类...")
            manager.create_category(
                name="个人偏好",
                description="用户的个人喜好和偏好",
                parent=None
            )
            manager.create_category(
                name="工作信息",
                description="与工作相关的信息",
                parent=None
            )
            
            assert len(manager.categories) == 2
            print(f"✅ 创建 {len(manager.categories)} 个分类")
            
            # 测试 4.2: 添加记忆到分类
            print("\n[4.2] 添加记忆到分类...")
            manager.add_memory_to_category("个人偏好", "memory_id_1")
            manager.add_memory_to_category("个人偏好", "memory_id_2")
            manager.add_memory_to_category("工作信息", "memory_id_3")
            
            pref_category = manager.get_category("个人偏好")
            assert len(pref_category.memory_ids) == 2
            print(f"✅ '个人偏好' 分类包含 {len(pref_category.memory_ids)} 个记忆")
            
            # 测试 4.3: 获取所有分类
            print("\n[4.3] 获取所有分类...")
            all_categories = manager.get_all_categories()
            assert len(all_categories) == 2
            for cat in all_categories:
                print(f"   - {cat.name}: {len(cat.memory_ids)} 个记忆")
            print("✅ 获取所有分类成功")
            
            # 测试 4.4: 持久化
            print("\n[4.4] 测试持久化...")
            manager.save()
            
            # 创建新实例并加载
            manager2 = CategoryManager(storage_dir=self.temp_dir)
            assert len(manager2.categories) == 2
            print("✅ 持久化和加载成功")
            
            print("\n✅ 阶段 4 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 4 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_memory_graph(self) -> bool:
        """
        阶段 5: 记忆图谱测试
        
        测试内容：
        - 添加节点
        - 添加关系
        - 查询相关节点
        - 持久化
        """
        print("\n" + "="*60)
        print("阶段 5: 记忆图谱测试 (MemoryGraph)")
        print("="*60)
        
        try:
            # 创建记忆图谱实例
            graph = MemoryGraph(storage_dir=self.temp_dir)
            
            # 测试 5.1: 添加节点
            print("\n[5.1] 添加节点...")
            graph.add_node("item_1", "用户喜欢晴天")
            graph.add_node("item_2", "用户讨厌下雨天")
            graph.add_node("item_3", "用户在北京工作")
            
            assert graph.node_count() == 3
            print(f"✅ 添加 {graph.node_count()} 个节点")
            
            # 测试 5.2: 添加关系
            print("\n[5.2] 添加关系...")
            graph.add_edge("item_1", "item_2", RelationType.OPPOSITE)
            graph.add_edge("item_3", "item_1", RelationType.RELATED)
            
            assert graph.edge_count() == 2
            print(f"✅ 添加 {graph.edge_count()} 条边")
            
            # 测试 5.3: 查询相关节点
            print("\n[5.3] 查询相关节点...")
            related = graph.get_related_nodes("item_1")
            assert len(related) >= 1
            print(f"✅ 'item_1' 有 {len(related)} 个相关节点")
            
            # 测试 5.4: 持久化
            print("\n[5.4] 测试持久化...")
            graph.save()
            
            # 创建新实例并加载
            graph2 = MemoryGraph(storage_dir=self.temp_dir)
            assert graph2.node_count() == 3
            assert graph2.edge_count() == 2
            print("✅ 持久化和加载成功")
            
            print("\n✅ 阶段 5 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 5 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_memory_manager(self) -> bool:
        """
        阶段 6: 记忆管理器集成测试
        
        测试内容：
        - 初始化管理器
        - 添加交互
        - 生成会话总结
        - 检索记忆
        """
        print("\n" + "="*60)
        print("阶段 6: 记忆管理器集成测试 (MemoryManager)")
        print("="*60)
        
        if not self.llm:
            print("⚠️  LLM 未初始化，跳过此阶段")
            return True
        
        try:
            # 测试 6.1: 初始化管理器
            print("\n[6.1] 初始化记忆管理器...")
            manager = MemoryManager(llm=self.llm, storage_dir=self.temp_dir)
            print("✅ 记忆管理器初始化成功")
            
            # 测试 6.2: 添加交互
            print("\n[6.2] 添加对话交互...")
            manager.add_interaction("你好", "你好！有什么可以帮助你的吗？")
            manager.add_interaction("今天天气怎么样？", "抱歉，我无法获取实时天气信息。")
            manager.add_interaction("那你能做什么？", "我可以回答问题、提供建议、帮助解决问题等。")
            
            # 检查短期记忆
            messages = manager.short_term.get_messages()
            assert len(messages) == 6  # 3对对话，6条消息
            print(f"✅ 添加 {len(messages)} 条消息到短期记忆")
            
            # 测试 6.3: 生成会话总结
            print("\n[6.3] 生成会话总结...")
            history = manager.short_term.get_messages()
            summary_text = await manager.summarize_session(history, "test_session_integration")
            
            if summary_text:
                print(f"✅ 生成会话总结成功")
                print(f"   总结: {summary_text[:100]}...")
            else:
                print("⚠️  会话总结生成失败（可能是 LLM API 问题）")
            
            # 测试 6.4: 检索记忆
            print("\n[6.4] 检索短期记忆...")
            context = manager.get_short_term_context()
            assert len(context) > 0
            print(f"✅ 检索到 {len(context)} 条短期记忆")
            
            print("\n✅ 阶段 6 测试通过")
            return True
            
        except Exception as e:
            print(f"\n❌ 阶段 6 测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False


async def main():
    """主测试函数"""
    print("="*60)
    print("🚀 记忆系统模块测试")
    print("="*60)
    
    tester = MemoryTester()
    tester.setup()
    
    try:
        # 按顺序执行测试
        tests = [
            ("短期记忆", tester.test_short_term_memory),
            ("会话总结存储", tester.test_session_summary_store),
            ("记忆项存储", tester.test_memory_item_store),
            ("分类管理器", tester.test_category_manager),
            ("记忆图谱", tester.test_memory_graph),
            ("记忆管理器集成", tester.test_memory_manager),
        ]
        
        results = []
        for test_name, test_func in tests:
            result = await test_func()
            results.append((test_name, result))
        
        # 打印测试总结
        print("\n" + "="*60)
        print("测试总结")
        print("="*60)
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = "✅ 通过" if result else "❌ 失败"
            print(f"{test_name}: {status}")
        
        print("="*60)
        print(f"总计: {passed}/{total} 通过")
        
        if passed == total:
            print("✨ 所有测试通过！")
            return True
        else:
            print(f"⚠️  {total - passed} 个测试失败")
            return False
        
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        tester.cleanup()


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(1)
