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

# ====== 麦克风VAD参数 ======
MIC_THRESHOLD = 400     # 音量门限，建议800~1200
START_FRAMES = 1          # 连续5帧认为开始讲话
END_FRAMES = 20           # 连续20帧认为结束讲话


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
    speaking = False
    speech_count = 0
    silence_count = 0

    while not stop_event.is_set():
        indata = await stream.read()

        # 计算RMS音量
        rms = np.sqrt(np.mean(indata.astype(np.float32) ** 2))

        if rms >= MIC_THRESHOLD:
            speech_count += 1
            silence_count = 0
        else:
            silence_count += 1
            speech_count = 0

        # ---------- 未讲话 ----------
        if not speaking:
            if speech_count >= START_FRAMES:
                speaking = True
                print("\n🎤 Speech Started")

            else:
                continue

        # ---------- 已讲话 ----------
        await ws.send(indata.tobytes())

        # ---------- 判断结束 ----------
        if silence_count >= END_FRAMES:
            speaking = False
            speech_count = 0
            silence_count = 0
            print("\n🔇 Speech End")


async def receive_results(ws, output_path: str):
    accumulated = ""  # partial chunks within one speech segment
    async for message in ws:
        data = json.loads(message)
        is_final = data.get("is_final", False)
        text = data.get("text", "")

        # 之前这里 `if not text: continue` 会把 text 为空的 is_final=True 消息也直接
        # 丢弃掉——但服务端在"这一段的最后一块音频没识别出新内容"时，text 恰好就是空的，
        # 于是客户端永远收不到"本段结束"的信号，之前已经攒下的 accumulated 内容
        # （比如"不"）就卡住了，既不会打印 [final]，也不会清空、进入下一轮。
        # 现在把 is_final 判断提到最前面：只要是 is_final=True，无论 text 是否为空，
        # 都用 accumulated + text 兜底完成这一轮。
        if is_final:
            full_text = accumulated + text
            accumulated = ""
            if not full_text:
                # 真正没有任何有效内容（比如纯静音误触发），不打印、不发给LLM
                continue
            # Clear the partial preview line then print final on its own line
            print(f"\r\033[K[final] {full_text}", flush=True)
            chat_with_streaming_response(full_text)
            save_text(full_text, output_path)
        elif text:
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