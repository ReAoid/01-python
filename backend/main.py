import sys
import logging
from pathlib import Path
import asyncio

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import settings

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.system.log_level.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
app = FastAPI(
    title="灵依 Backend API",
    description="灵依 智能助手后端服务",
    version="1.0.0"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 定义路径
frontend_path = project_root / "frontend"

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
    # 假设模型路径遵循约定
    return JSONResponse({
        "character_name": char_name,
        "model_path": f"/static/live2d/{char_name}/{char_name}.model3.json"
    })


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket 聊天接口"""
    # 延迟导入，避免启动时的依赖问题
    try:
        from backend.brain import SessionManager
    except ImportError as e:
        logger.error(f"无法导入 SessionManager: {e}")
        await websocket.close(code=1011, reason="Server configuration error")
        return
    
    await websocket.accept()
    logger.info("WebSocket 连接已建立")
    
    queue = asyncio.Queue()
    session = SessionManager(message_queue=queue)
    
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
    logger.info(f"静态文件目录: {frontend_path}")

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
