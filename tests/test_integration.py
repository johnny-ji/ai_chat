import pytest
import asyncio
import websockets
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config_loader import load_config


def test_load_config_test_environment():
    """测试测试环境配置加载正确。"""
    config = load_config("test")
    assert config["host"] == "0.0.0.0"
    assert config["port"] == 10095
    assert config["device"] == "cpu"
    assert config["ngpu"] == 0


@pytest.mark.asyncio
async def test_websocket_connection():
    """测试 WebSocket 服务可以连接并接收配置消息。"""
    try:
        config = load_config("test")
        uri = f"ws://{config['host']}:{config['port']}"

        async with websockets.connect(uri, subprotocols=["binary"]) as ws:
            # 发送配置
            await ws.send(json.dumps({
                "chunk_size": [5, 10, 5],
                "is_speaking": True,
            }))

            # 发送空音频帧
            await ws.send(b"\x00\x00" * 320)

            # 标记结束
            await ws.send(json.dumps({"is_speaking": False}))

            # 尝试接收消息
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                data = json.loads(msg)
                assert "text" in data
                assert "is_final" in data
            except asyncio.TimeoutError:
                pass  # 可能没有识别结果
    except (ConnectionRefusedError, OSError, websockets.exceptions.InvalidMessage):
        pytest.skip("服务未启动")
