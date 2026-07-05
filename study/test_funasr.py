# test_funasr.py
import asyncio
import json
import wave
import websockets

async def test():
    uri = "ws://192.168.140.180:10095"
    async with websockets.connect(uri) as ws:
        # 发初始化帧
        await ws.send(json.dumps({
            "mode": "2pass",
            "chunk_size": [0, 10, 5],
            "wav_name": "test",
            "is_speaking": True,
            "itn": True,
        }))

        # 发一段测试 WAV 文件（16kHz PCM16 mono）
        with wave.open("q1.wav", "rb") as wf:
            while True:
                data = wf.readframes(800)   # 每次读 50ms
                if not data:
                    break
                await ws.send(data)
                await asyncio.sleep(0.05)

        # 结束
        await ws.send(json.dumps({"is_speaking": False}))

        # 接收结果
        async for msg in ws:
            result = json.loads(msg)
            if result.get("text"):
                print("识别结果:", result["text"])
            if result.get("is_final"):
                break

asyncio.run(test())