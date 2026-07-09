import asyncio
import argparse
import json
import os
import sys
from datetime import datetime
import numpy as np
import sounddevice as sd
import websockets
from llm_util import chat_with_streaming_response


# ====== 配置 ======
SAMPLE_RATE = 16000
CHANNELS = 1
BLOCK_SIZE = 960
DTYPE = "int16"


# ====== 命令行参数 ======
def parse_args(args=None):
    parser = argparse.ArgumentParser(description="FunASR 实时流式语音客户端")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="服务端地址")
    parser.add_argument("--port", type=int, default=10095, help="服务端端口")
    return parser.parse_args(args)


# ====== 结果保存 ======
def get_output_path() -> str:
    os.makedirs("outputs", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"outputs/FunASR_{timestamp}.txt"


def save_text(text: str, output_path: str):
    with open(output_path, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {text}\n")


# ====== 麦克风录音 ======
class MicrophoneStream:
    """封装 sounddevice 录音"""
    def __init__(self):
        self.queue = asyncio.Queue()
        self._loop = None

    def callback(self, indata, frames, time_info, status):
        # sounddevice calls this from a non-asyncio thread;
        # call_soon_threadsafe wakes up the event loop so queue.get() unblocks.
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self.queue.put_nowait, indata.copy())

    async def __aenter__(self):
        self._loop = asyncio.get_event_loop()
        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=BLOCK_SIZE,
            callback=self.callback,
        )
        self.stream.start()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.stream.stop()
        self.stream.close()

    async def read(self):
        return await self.queue.get()


# ====== WebSocket 通信 ======
async def send_audio(ws, stream: MicrophoneStream, stop_event: asyncio.Event):
    frame_count = 0
    while not stop_event.is_set():
        indata = await stream.read()
        await ws.send(indata.tobytes())
        frame_count += 1


async def receive_results(ws, output_path: str):
    accumulated = ""  # partial chunks within one speech segment
    async for message in ws:
        data = json.loads(message)
        is_final = data.get("is_final", False)
        text = data.get("text", "")
        if not text:
            continue
        if is_final:
            full_text = accumulated + text
            # Clear the partial preview line then print final on its own line
            print(f"\r\033[K[final] {full_text}", flush=True)
            chat_with_streaming_response(full_text)
            save_text(full_text, output_path)
            accumulated = ""
        else:
            accumulated += text
            # Show only the last 60 chars so the line never wraps
            preview = ("..." + accumulated[-57:]) if len(accumulated) > 60 else accumulated
            print(f"\r\033[K[...] {preview}", end="", flush=True)


# ====== 主函数 ======
async def main():
    args = parse_args()
    output_path = get_output_path()
    uri = f"ws://{args.host}:{args.port}"

    print(f"Connecting to {uri}...")
    async with websockets.connect(uri, subprotocols=["binary"], ping_interval=None) as ws:
        print("Connected.")

        # 发送配置
        await ws.send(json.dumps({
            "chunk_size": [5, 10, 5],
            "chunk_interval": 10,
            "is_speaking": True,
        }))
        print("Start speaking... (Press Ctrl+C to stop)")
        print(f"Results will be saved to: {output_path}")
        import sys; sys.stdout.flush()

        async with MicrophoneStream() as stream:
            stop_event = asyncio.Event()
            send_task = asyncio.create_task(send_audio(ws, stream, stop_event))
            recv_task = asyncio.create_task(receive_results(ws, output_path))

            try:
                await asyncio.gather(send_task, recv_task)
            except (KeyboardInterrupt, asyncio.CancelledError):
                print("\nStopping...")
            finally:
                stop_event.set()
                send_task.cancel()
                try:
                    # 通知服务端结束
                    await ws.send(json.dumps({"is_speaking": False}))
                    # 等待最后的识别结果
                    await asyncio.wait_for(recv_task, timeout=3.0)
                except Exception:
                    recv_task.cancel()
                    try:
                        await recv_task
                    except asyncio.CancelledError:
                        pass
                print(f"Results saved to: {output_path}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nClient stopped.")
