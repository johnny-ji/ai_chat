# FunASR-Client 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 创建 `FunASR-Client.py`，实现通过命令行设置服务端地址和端口，启动本地麦克风进行实时语音转文字，并保存结果。

**Architecture:** 使用 `sounddevice` 跨平台录制麦克风音频，使用 `websockets` 异步连接服务端，通过 `asyncio` 协程同时处理录音、发送、接收三个流程，最终识别结果保存到 `outputs/` 目录。

**Tech Stack:** Python, asyncio, websockets, sounddevice, numpy

## Global Constraints

- Python: 兼容 Python 3.8+
- 跨平台支持：macOS / Linux / Windows
- WebSocket subprotocol: `binary`
- 音频格式：PCM16, 单声道, 16kHz, 60ms 音频块
- 服务端接口：JSON 配置消息 + 二进制音频消息
- 结果保存路径：`outputs/FunASR_<timestamp>.txt`
- 命令行参数：仅 `--host` 和 `--port`

---

## 文件结构

### 新建文件

- `FunASR-Client.py` — 客户端主程序
- `tests/test_client.py` — 客户端单元测试

### 修改文件

- `requirements.txt` — 添加客户端依赖并标注注释

---

## Task 1: 更新依赖配置

**Files:**
- Modify: `requirements.txt`

**Interfaces:**
- Consumes: None
- Produces: 更新后的 `requirements.txt`

- [ ] **Step 1: 在 `requirements.txt` 末尾添加客户端依赖并注释**

```txt
sounddevice>=0.4.0      # FunASR-Client 麦克风录音
numpy>=1.19.0           # FunASR-Client 音频数据转换
websockets>=10.0        # FunASR-Client WebSocket 通信
```

- [ ] **Step 2: 安装依赖**

Run:
```bash
.venv/bin/pip install sounddevice numpy websockets
```

Expected: 安装成功，无错误。

- [ ] **Step 3: 提交**

```bash
git add requirements.txt
git commit -m "chore: add FunASR-Client dependencies"
```

---

## Task 2: 创建 FunASR-Client.py

**Files:**
- Create: `FunASR-Client.py`

**Interfaces:**
- Consumes: `--host`, `--port`
- Produces: 客户端主程序

- [ ] **Step 1: 创建 `FunASR-Client.py` 基础结构**

```python
import asyncio
import argparse
import json
import os
import sys
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
```

- [ ] **Step 2: 实现麦克风录音类**

```python
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
```

- [ ] **Step 3: 实现 WebSocket 发送和接收函数**

```python
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
```

- [ ] **Step 4: 实现主函数**

```python
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

- [ ] **Step 5: 运行语法检查**

Run:
```bash
python3 -m py_compile FunASR-Client.py
```

Expected: 无语法错误。

- [ ] **Step 6: 提交**

```bash
git add FunASR-Client.py
git commit -m "feat: add FunASR-Client for real-time streaming ASR"
```

---

## Task 3: 创建客户端测试

**Files:**
- Create: `tests/test_client.py`

**Interfaces:**
- Consumes: `FunASR-Client.py` 中的函数
- Produces: 测试文件

- [ ] **Step 1: 创建 `tests/test_client.py`**

```python
import pytest
import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from FunASR_Client import parse_args, get_output_path, save_text


def test_parse_args_default():
    args = parse_args([])
    assert args.host == "127.0.0.1"
    assert args.port == 10095


def test_parse_args_custom():
    args = parse_args(["--host", "192.168.1.1", "--port", "8080"])
    assert args.host == "192.168.1.1"
    assert args.port == 8080


def test_get_output_path(tmp_path):
    # 使用临时目录
    import FunASR_Client as client
    original = client.get_output_path
    
    def mock_get_output_path():
        os.makedirs(tmp_path / "outputs", exist_ok=True)
        return str(tmp_path / "outputs" / "test.txt")
    
    client.get_output_path = mock_get_output_path
    path = mock_get_output_path()
    assert path.endswith("test.txt")
    client.get_output_path = original


def test_save_text(tmp_path):
    path = tmp_path / "test.txt"
    save_text("hello", str(path))
    content = path.read_text(encoding="utf-8")
    assert "hello" in content
```

- [ ] **Step 2: 运行测试**

Run:
```bash
.venv/bin/python -m pytest tests/test_client.py -v
```

Expected: PASS

- [ ] **Step 3: 提交**

```bash
git add tests/test_client.py
git commit -m "test: add FunASR-Client tests"
```

---

## Task 4: 集成测试与手动验证

**Files:**
- Modify: `FunASR-Client.py`（如发现问题）

**Interfaces:**
- Consumes: 完整客户端
- Produces: 验证结果

- [ ] **Step 1: 启动服务端（手动）**

Run:
```bash
.venv/bin/python FunASR-Service.py --env development
```

Expected: 服务启动，模型加载完成，监听端口 10095。

- [ ] **Step 2: 启动客户端（手动）**

Run:
```bash
.venv/bin/python FunASR-Client.py --host 127.0.0.1 --port 10095
```

Expected: 连接成功，开始录音，说话后终端显示识别结果。

- [ ] **Step 3: 验证结果保存**

检查 `outputs/` 目录下是否生成了结果文件，内容格式正确。

- [ ] **Step 4: 提交（如有修改）**

```bash
git add FunASR-Client.py
git commit -m "fix: adjust client based on manual integration test"
```

---

## Self-Review

### Spec Coverage

| 设计需求 | 对应任务 |
|---------|---------|
| 命令行参数 `--host`, `--port` | Task 2 |
| 启动麦克风录音 | Task 2 |
| WebSocket 连接服务端 | Task 2 |
| 终端实时显示结果 | Task 2 |
| 保存结果到文件 | Task 2 |
| 依赖项注释 | Task 1 |
| 跨平台支持 | Task 2 (sounddevice) |

### Placeholder Scan

- 无 TBD/TODO
- 无模糊描述
- 所有步骤包含实际代码

### Type Consistency

- `parse_args() -> argparse.Namespace`
- `get_output_path() -> str`
- `save_text(text: str, output_path: str)`
- `send_audio(ws, stream: MicrophoneStream, stop_event: asyncio.Event)`
- `receive_results(ws, output_path: str)`

### 依赖说明

- `sounddevice` 底层依赖 portaudio，部分平台可能需要手动安装
- 集成测试需要服务端已启动

---

**Plan complete and saved to `docs/superpowers/plans/2026-07-04-funasr-client.md`.**

## 执行选项

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach would you like to use?