import sys
import logging
from pathlib import Path
import asyncio

# 将项目根目录添加到 python path，确保可以导入 backend 模块
sys.path.append(str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.brain import SessionManager

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="N.E.K.O Backend API")

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该限制来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件
# 假设 static 目录在 backend 同级或 frontend 目录下
# 这里暂时只挂载 frontend 目录用于测试
frontend_path = Path(__file__).resolve().parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

@app.get("/")
async def get_index():
    """返回前端主页"""
    index_path = frontend_path / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
    return JSONResponse(status_code=404, content={"message": "Frontend index.html not found"})

@app.get("/api/config/page_config")
async def get_page_config():
    """
    返回页面基础配置
    前端根据此配置加载对应的 Live2D 模型
    """
    return JSONResponse({
        "character_name": "feibi",
        # 这里应该指向实际的模型文件路径
        # 如果模型文件在 static/live2d/... 下，则路径应为 /static/live2d/...
        "model_path": "/static/live2d/feibi/feibi.model3.json" 
    })

@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 聊天接口
    连接建立后，初始化 SessionManager 并启动会话循环
    """
    await websocket.accept()
    logger.info("WebSocket connection accepted")
    
    # 创建消息队列 (用于组件间通信)
    queue = asyncio.Queue()
    
    # 初始化会话管理器
    session = SessionManager(message_queue=queue)
    
    try:
        # 启动会话
        # start() 方法会运行内部的监听循环，直到连接断开
        await session.start(websocket)
        
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"WebSocket session error: {e}", exc_info=True)
        # 尝试发送错误信息给前端（如果连接还活着）
        try:
            await websocket.close(code=1011)
        except:
            pass
    finally:
        # 确保清理资源
        if session.is_active:
            await session.stop()
        logger.info("WebSocket session closed")

if __name__ == "__main__":
    import uvicorn
    # 启动服务器
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
