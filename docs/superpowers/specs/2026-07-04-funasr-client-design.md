# FunASR 实时流式语音客户端设计

**日期**: 2026-07-04  
**目标**: 创建 FunASR-Client.py，实现通过命令行设置服务端地址和端口，启动本地麦克风进行实时语音转文字  
**作者**: Claude Code

---

## 1. 需求概览

### 1.1 核心需求
- 通过命令行设置服务器地址和端口号
- 启动本地麦克风进行实时录音
- 将音频流实时发送到 FunASR 服务端
- 在终端实时显示识别结果
- 将识别结果保存到本地文本文件
- 服务端 VAD 自动检测语音结束
- 用户可通过 `Ctrl+C` 结束客户端

### 1.2 技术约束
- 跨平台支持：Mac / Linux / Windows
- 使用 Python 实现
- 使用 `sounddevice` 进行麦克风录音
- 使用 `websockets` 与服务端通信
- 音频格式：PCM16，单声道，16kHz

---

## 2. 架构设计

### 2.1 系统架构

```
┌─────────────────┐         WebSocket          ┌──────────────────┐
│   FunASR-Client│  ───────────────────────►  │   FunASR-Service │
│                 │                              │                  │
│  ┌──────────┐ │                              │  ┌──────────┐   │
│  │ 麦克风录音 │ │  ──►  ┌──────────┐  ──►     │  │   VAD    │   │
│  │sounddevice│ │       │ WebSocket│          │  │ 流式 ASR │   │
│  └──────────┘ │  ◄──  │  客户端   │  ◄──     │  │  标点    │   │
│       ▲       │       └──────────┘          │  └──────────┘   │
│       │       │                              │                  │
│  ┌──────────┐ │                              └──────────────────┘
│  │ 结果保存  │ │
│  │ 终端显示  │ │
│  └──────────┘ │
└─────────────────┘
```

### 2.2 数据流

**启动流程：**
```
1. 解析命令行：--host, --port
2. 连接 WebSocket: ws://host:port
3. 发送 JSON 配置消息：
   {
     "chunk_size": [5, 10, 5],
     "is_speaking": true
   }
4. 启动麦克风录音
5. 循环：
   - 读取音频块（60ms / 960 samples）
   - 发送二进制数据到服务端
   - 接收并处理返回结果
```

**结果处理：**
```
服务端返回：
{
  "text": "识别结果",
  "wav_name": "microphone",
  "is_final": true/false
}


客户端处理：
- is_final=false: 终端显示 "[partial] 识别结果"
- is_final=true:  终端显示 "[final] 识别结果", 写入文件
```

---

## 3. 功能设计

### 3.1 命令行参数

```bash
python FunASR-Client.py --host 127.0.0.1 --port 10095
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--host` | str | `127.0.0.1` | 服务端地址 |
| `--port` | int | `10095` | 服务端端口 |

### 3.2 录音参数

```python
SAMPLE_RATE = 16000      # 16kHz，与服务端一致
CHANNELS = 1             # 单声道
BLOCK_SIZE = 960         # 60ms 音频块
DTYPE = "int16"          # PCM16
```

### 3.3 WebSocket 通信

**连接：**
```python
uri = f"ws://{host}:{port}"
async with websockets.connect(uri, subprotocols=["binary"]) as ws:
    # 发送配置
    await ws.send(json.dumps({
        "chunk_size": [5, 10, 5],
        "is_speaking": True,
    }))
    # 启动录音和发送
```

**发送音频：**
```python
# 录音回调
async def audio_callback(indata, frames, time_info, status):
    await ws.send(indata.tobytes())
```

**接收结果：**
```python
async def receive_results():
    async for message in ws:
        data = json.loads(message)
        if data.get("is_final"):
            print(f"[final] {data['text']}")
            save_to_file(data["text"])
        else:
            print(f"[partial] {data['text']}")
```

### 3.4 结果保存

**保存路径：**
```
outputs/FunASR_<timestamp>.txt
```

**保存格式：**
```
[2026-07-04 14:30:25] final: 这是一段识别结果
[2026-07-04 14:30:28] final: 这是另一段识别结果
```

---

## 4. 代码结构

```python
import asyncio
import argparse
import json
import os
import sys
import time
from datetime import datetime
import numpy as np
import sounddevice as sd
import websockets


# ====== 配置 ======
SAMPLE_RATE = 16000
CHANNELS = 1
BLOCK_SIZE = 960
DTYPE = "int16"


# ====== 命令行参数 ======
def parse_args():
    parser = argparse.ArgumentParser(description="FunASR 实时流式语音客户端")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="服务端地址")
    parser.add_argument("--port", type=int, default=10095, help="服务端端口")
    return parser.parse_args()


# ====== 结果保存 ======
def get_output_path() -> str:
    os.makedirs("outputs", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"outputs/FunASR_{timestamp}.txt"


def save_text(text: str, output_path: str):
    with open(output_path, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {text}\n")


# ====== 音频录制 ======
class MicrophoneStream:
    """封装 sounddevice 录音"""
    def __init__(self):
        self.queue = asyncio.Queue()

    def callback(self, indata, frames, time_info, status):
        self.queue.put_nowait(indata.copy())

    async def __aenter__(self):
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


# ====== WebSocket 客户端 ======
async def send_audio(ws, stream: MicrophoneStream, stop_event: asyncio.Event):
    while not stop_event.is_set():
        indata = await stream.read()
        await ws.send(indata.tobytes())


async def receive_results(ws, output_path: str):
    async for message in ws:
        data = json.loads(message)
        is_final = data.get("is_final", False)
        text = data.get("text", "")
        if not text:
            continue
        if is_final:
            print(f"[final] {text}")
            save_text(text, output_path)
        else:
            print(f"[partial] {text}")


# ====== 主函数 ======
async def main():
    args = parse_args()
    output_path = get_output_path()
    uri = f"ws://{args.host}:{args.port}"

    print(f"Connecting to {uri}...")
    async with websockets.connect(uri, subprotocols=["binary"]) as ws:
        print("Connected.")

        # 发送配置
        await ws.send(json.dumps({
            "chunk_size": [5, 10, 5],
            "is_speaking": True,
        }))
        print("Start speaking... (Press Ctrl+C to stop)")

        output_path = get_output_path()
        print(f"Results will be saved to: {output_path}")

        async with MicrophoneStream() as stream:
            stop_event = asyncio.Event()
            send_task = asyncio.create_task(send_audio(ws, stream, stop_event))
            recv_task = asyncio.create_task(receive_results(ws, output_path))

            try:
                await asyncio.gather(send_task, recv_task)
            except KeyboardInterrupt:
                print("\nStopping...")
                stop_event.set()
                send_task.cancel()
                # 通知服务端结束
                await ws.send(json.dumps({"is_speaking": False}))
                # 等待最后的识别结果
                try:
                    await asyncio.wait_for(recv_task, timeout=3.0)
                except asyncio.TimeoutError:
                    recv_task.cancel()
                print(f"Results saved to: {output_path}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nClient stopped.")
```

---

## 5. 错误处理

| 场景 | 处理方式 |
|------|---------|
| 连接失败 | 打印错误信息，退出程序 |
| 录音设备不存在 | 提示用户检查麦克风 |
| 用户 Ctrl+C | 发送 `is_speaking=false`，关闭连接，保存文件 |
| 服务端断开 | 停止录音，保存已识别结果 |

---

## 6. 依赖项

新增到 `requirements.txt`（需添加 FunASR-Client 使用注释）：

```txt
sounddevice>=0.4.0      # FunASR-Client 麦克风录音
numpy>=1.19.0           # FunASR-Client 音频数据转换
websockets>=10.0        # FunASR-Client WebSocket 通信
```

---

## 7. 测试计划

### 7.1 单元测试

- [ ] 命令行参数解析
- [ ] 输出文件路径生成
- [ ] 文本保存格式

### 7.2 集成测试

- [ ] 音频数据格式转换（float32 -> int16）
- [ ] WebSocket 连接和消息格式（使用 mock 服务端）

### 7.3 手动测试

- [ ] 连接本地 FunASR-Service
- [ ] 使用麦克风说话，观察终端输出
- [ ] 检查输出文件内容

---

## 8. 兼容性说明

### 8.1 平台差异

| 平台 | 依赖安装 | 说明 |
|------|---------|------|
| macOS | `pip install sounddevice` | 可能需要安装 portaudio |
| Linux | `pip install sounddevice` | 可能需要安装 portaudio19-dev |
| Windows | `pip install sounddevice` | 通常无需额外依赖 |

### 8.2 注意事项

- 确保麦克风权限已开启
- 确保服务端已启动并可访问
- 网络延迟可能影响实时性

---

## 9. 后续扩展建议

如需在未来增强客户端，可考虑：

1. **多麦克风选择**：增加 `--device` 参数选择录音设备
2. **音量阈值**：增加静音检测，减少无效数据发送
3. **音频文件输入**：支持从 WAV 文件读取音频
4. **图形界面**：增加简单的 UI
5. **热词支持**：支持通过命令行传入热词

---

## 10. 审批记录

| 版本 | 日期 | 变更内容 | 审批人 |
|------|------|---------|--------|
| v1.0 | 2026-07-04 | 初始设计 | - |

---

**状态**: ⏳ 等待审批  
**下一步**: 用户确认后创建实现计划
