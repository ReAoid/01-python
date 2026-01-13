import sys
import logging
import json
from pathlib import Path
import asyncio
from contextlib import asynccontextmanager

from backend.core.logger import init_logging, shutdown_logging

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import settings, paths, prompts
from backend.core.event_bus import event_bus, EventType
from backend.services.memory_service import MemoryService
from backend.services.task_service import TaskService
from backend.services.self_awareness_service import SelfAwarenessService

# 初始化统一日志系统（中央队列 + loguru）
init_logging(
    log_level=settings.system.log_level,
    log_file=str(paths.LOGS_DIR / "backend.log"),  # 后端总日志文件
    rotation="10 MB",
    retention="7 days",
)
logger = logging.getLogger(__name__)

# 定义路径
frontend_path = project_root / "frontend"

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # Startup - 启动时执行
    logger.info("正在初始化后台服务...")
    
    # 打印静态文件目录信息
    if frontend_path.exists():
        logger.info(f"静态文件目录: {frontend_path}")

    try:
        # 初始化服务 (它们会自动订阅事件总线)
        # 存储在 app.state 中以保持引用存活
        app.state.memory_service = MemoryService()
        # app.state.task_service = TaskService() # todo 暂时关闭
        # app.state.self_awareness_service = SelfAwarenessService() # todo 暂时关闭
        
        # 通知系统启动
        await event_bus.publish(EventType.SYSTEM_STARTUP, {})
        logger.success("后台服务已成功初始化")
    except Exception as e:
        logger.error(f"启动后台服务失败: {e}")
    
    yield  # 应用运行期间
    
    # Shutdown - 关闭时执行
    shutdown_logging()

# 创建 FastAPI 应用
app = FastAPI(
    title="灵依 Backend API",
    description="灵依 智能助手后端服务",
    version="1.0.0",
    lifespan=lifespan
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# 路由定义
# ============================================================================

@app.get("/")
async def root():
    """根路径 - 返回前端页面或 API 信息"""
    index_path = frontend_path / "index.html"
    
    if index_path.exists():
        try:
            return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"读取 index.html 失败: {e}")
    
    # 如果没有前端文件，返回 API 信息
    return JSONResponse({
        "name": "灵依 Backend API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "config": "/api/config/page_config",
            "websocket": "/ws/chat",
            "docs": "/docs"
        }
    })


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return JSONResponse({
        "status": "healthy",
        "service": "灵依 Backend API",
        "version": "1.0.0"
    })


@app.get("/api/config/page_config")
async def get_page_config():
    """获取页面配置"""
    char_name = settings.tts.active_character
    
    # 从 prompts.py 中加载角色人设参数
    first_mes = prompts.CHARACTER_PERSONA.get('first_mes', '你好！我是你的私人AI助手。有什么我可以帮你的吗？')
    
    # 假设模型路径遵循约定
    return JSONResponse({
        "character_name": char_name,
        "model_path": f"/static/live2d/{char_name}/{char_name}.model3.json",
        "first_message": first_mes
    })


@app.get("/api/config/system")
async def get_system_config():
    """
    获取系统配置信息
    
    Returns:
        系统配置数据，包括输入输出模式、AI助手配置、音频配置、系统配置等
    """
    try:
        # 构建配置响应数据
        config_data = {
            # 输入输出模式配置
            "input_output": {
                "input_mode": "text",  # 默认文本输入模式
                "output_mode": "text_only",  # 默认纯文本输出模式
                "available_input_modes": ["text", "audio"],
                "available_output_modes": ["text_only", "text_audio"]
            },
            
            # AI助手配置
            "ai_assistant": {
                "character_name": settings.tts.active_character,
                "display_name": prompts.CHARACTER_PERSONA.get('name', '灵依'),
                "description": prompts.CHARACTER_PERSONA.get('description', ''),
                "personality": prompts.CHARACTER_PERSONA.get('personality', ''),
                "first_message": prompts.CHARACTER_PERSONA.get('first_mes', '')
            },
            
            # 大语言模型配置
            "llm": {
                "chat_model": settings.chat_llm.model,
                "chat_provider": settings.chat_llm.provider,
                "temperature": settings.chat_llm.temperature,
                "max_tokens": settings.chat_llm.max_tokens,
                "embedding_model": settings.embedding_llm.model
            },
            
            # TTS配置
            "tts": {
                "enabled": settings.tts.enabled,
                "engine": settings.tts.engine,
                "active_character": settings.tts.active_character,
                "language": settings.tts.language,
                "server_host": settings.tts.server.host,
                "server_port": settings.tts.server.port,
                "auto_start": settings.tts.server.auto_start
            },
            
            # ASR配置
            "asr": {
                "enabled": settings.asr.enabled,
                "engine": settings.asr.engine,
                "model": settings.asr.model,
                "language": settings.asr.language,
                "sample_rate": settings.asr.audio.sample_rate,
                "channels": settings.asr.audio.channels
            },
            
            # 记忆系统配置
            "memory": {
                "max_history_length": settings.memory.max_history_length,
                "embedding_model": settings.embedding_llm.model,
                "retrieval_top_k": settings.memory.retrieval_top_k,
                "retrieval_threshold": settings.memory.retrieval_threshold,
                "min_summaries_for_structuring": settings.memory.min_summaries_for_structuring
            },
            
            # 用户档案配置
            "user_profile": {
                "name": settings.user_profile.name,
                "nickname": settings.user_profile.nickname,
                "age": settings.user_profile.age,
                "gender": settings.user_profile.gender,
                "relationship_with_ai": settings.user_profile.relationship_with_ai
            },
            
            # 系统配置
            "system": {
                "app_name": settings.app_name,
                "debug": settings.system.debug,
                "log_level": settings.system.log_level,
                "data_dir": settings.system.data_dir
            }
        }
        
        return JSONResponse(content=config_data)
        
    except Exception as e:
        logger.error(f"获取系统配置失败: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to get system config: {str(e)}"}
        )


# ============================================================================
# 历史记录 API 路由
# ============================================================================

@app.get("/api/history/sessions")
async def get_history_sessions(count: int = 10):
    """
    获取最近的对话会话列表
    
    Args:
        count: 返回数量，默认10条
    
    Returns:
        会话列表，包含 session_id, summary, key_points, message_count, created_at, has_raw_conversation
    """
    try:
        memory_service = app.state.memory_service
        if not memory_service:
            return JSONResponse(
                status_code=503,
                content={"error": "Memory service not available"}
            )
        
        # 获取最近的会话总结
        summaries = memory_service.memory_manager.get_recent_summaries(count)
        
        # 检查是否存在原始对话文件
        sessions_dir = memory_service.memory_manager.structurer.sessions_dir
        
        result = []
        for summary in summaries:
            session_file = sessions_dir / f"{summary.session_id}.json"
            result.append({
                "session_id": summary.session_id,
                "summary": summary.summary,
                "key_points": summary.key_points,
                "message_count": summary.message_count,
                "created_at": summary.created_at.isoformat(),
                "has_raw_conversation": session_file.exists()
            })
        
        return JSONResponse(content=result)
        
    except Exception as e:
        logger.error(f"获取历史会话失败: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to get history: {str(e)}"}
        )


@app.get("/api/history/session/{session_id}")
async def get_session_detail(session_id: str):
    """
    获取指定会话的完整原始对话记录
    
    Args:
        session_id: 会话ID（如 session_2026-01-08_15-23-36）
    
    Returns:
        完整的会话对话记录，包含 session_id, timestamp, message_count, messages
    """
    try:
        memory_service = app.state.memory_service
        if not memory_service:
            return JSONResponse(
                status_code=503,
                content={"error": "Memory service not available"}
            )
        
        # 读取原始对话文件
        sessions_dir = memory_service.memory_manager.structurer.sessions_dir
        session_file = sessions_dir / f"{session_id}.json"
        
        if not session_file.exists():
            return JSONResponse(
                status_code=404,
                content={"error": f"Session {session_id} not found"}
            )
        
        # 加载并返回原始对话
        with open(session_file, 'r', encoding='utf-8') as f:
            conversation_data = json.load(f)
        
        return JSONResponse(content=conversation_data)
        
    except Exception as e:
        logger.error(f"获取会话详情失败: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to get session detail: {str(e)}"}
        )


@app.get("/api/history/statistics")
async def get_history_statistics():
    """
    获取历史记录统计信息
    
    Returns:
        统计数据，包含总会话数、总记忆项数、按类型分布等
    """
    try:
        memory_service = app.state.memory_service
        if not memory_service:
            return JSONResponse(
                status_code=503,
                content={"error": "Memory service not available"}
            )
        
        # 获取统计信息
        stats = memory_service.memory_manager.get_statistics()
        
        # 构造前端友好的统计数据
        result = {
            "total_sessions": stats["summaries"]["total"],
            "unstructured_sessions": stats["summaries"]["unstructured"],
            "total_memory_items": stats["memory_items"]["total_items"],
            "memory_types": stats["memory_items"].get("type_distribution", {}),
            "categories": stats["memory_items"].get("category_distribution", {}),
            "short_term_messages": stats["short_term"]["message_count"]
        }
        
        return JSONResponse(content=result)
        
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to get statistics: {str(e)}"}
        )


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket 聊天接口"""
    # 延迟导入，避免启动时的依赖问题
    try:
        from backend.services.brain import SessionManager
    except ImportError as e:
        logger.error(f"无法导入 SessionManager: {e}")
        await websocket.close(code=1011, reason="Server configuration error")
        return
    
    await websocket.accept()
    logger.success("WebSocket 连接已成功建立")
    
    queue = asyncio.Queue()
    
    # 尝试复用全局 MemoryManager
    memory_manager = None
    if hasattr(app.state, "memory_service") and app.state.memory_service:
        memory_manager = app.state.memory_service.memory_manager

    session = SessionManager(message_queue=queue, memory_manager=memory_manager)
    
    try:
        await session.start(websocket)
    except WebSocketDisconnect:
        logger.info("客户端断开连接")
    except Exception as e:
        logger.error(f"WebSocket 会话错误: {e}", exc_info=True)
        try:
            await websocket.close(code=1011)
        except:
            pass
    finally:
        if hasattr(session, 'is_active') and session.is_active:
            await session.stop()
        logger.info("WebSocket 会话已关闭")


# 挂载静态文件（必须在路由定义之后）
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")

# ============================================================================
# 启动服务器
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    logger.info("=" * 70)
    logger.info("灵依 Backend API 启动中...")
    logger.info("=" * 70)
    logger.info(f"项目根目录: {project_root}")
    logger.info(f"前端目录: {frontend_path}")
    logger.info(f"前端存在: {frontend_path.exists()}")
    logger.info("")
    logger.info("注册的路由:")
    
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            methods = ', '.join(route.methods) if route.methods else 'WebSocket'
            logger.info(f"  [{methods:15}] {route.path}")
    
    logger.info("")
    logger.info("=" * 70)
    logger.info("服务器地址: http://127.0.0.1:8000")
    logger.info("API 文档: http://127.0.0.1:8000/docs")
    logger.info("=" * 70)
    logger.info("")
    
    # 启动服务器（不使用 reload，避免模块导入问题）
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
