"""main.py - FastAPI 入口，启动 WebSocket 服务"""
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn

from websocket_handler import handle_websocket

app = FastAPI(title="语音对话助手", version="1.0.0")

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    """根路由，返回主页面"""
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 端点"""
    await handle_websocket(websocket)


if __name__ == "__main__":
    print("=" * 60)
    print("语音对话助手服务")
    print("=" * 60)
    print("服务地址: http://localhost:8000")
    print("WebSocket: ws://localhost:8000/ws")
    print("=" * 60)

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
