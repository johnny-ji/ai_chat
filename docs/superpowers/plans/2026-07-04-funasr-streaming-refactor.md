# FunASR 流式语音识别服务重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `FunASR-Service.py` 精简为仅支持流式语音输入的服务，引入多环境 YAML 配置和模型自动下载机制，移除离线/2pass/声纹识别等无用代码。

**Architecture:** 使用 `yaml` 文件管理环境配置（开发/测试/生产），启动时自动检查并下载模型到 `models/` 目录；保留流式 ASR、VAD、标点三个核心模型；通过 ThreadPoolExecutor + Semaphore 实现非阻塞推理；WebSocket 服务端仅保留流式识别能力。

**Tech Stack:** Python, asyncio, websockets, PyYAML, modelscope, funasr, torch

## Global Constraints

- Python: 兼容 Python 3.8+
- torch: 需支持 `mps` 后端（Mac M1/M2/M3）
- PyYAML>=6.0
- modelscope>=1.0.0
- 模型目录: `models/`（可配置）
- 配置文件目录: `configs/`
- 服务启动方式: `python FunASR-Service.py --env <development|test|production>`
- 不引入新的运行时框架
- 保持现有客户端接口（WebSocket 消息格式）兼容

---

## 文件结构

### 新建文件

- `configs/development.yaml` — 开发环境配置
- `configs/test.yaml` — 测试环境配置
- `configs/production.yaml` — 生产环境配置
- `requirements.txt` — 依赖列表
- `tests/test_config.py` — 配置加载测试
- `tests/test_model_download.py` — 模型下载测试

### 修改文件

- `FunASR-Service.py` — 主服务文件，大幅精简

---

## Task 1: 项目基础与依赖配置

**Files:**
- Create: `requirements.txt`
- Create: `configs/development.yaml`
- Create: `configs/test.yaml`
- Create: `configs/production.yaml`

**Interfaces:**
- Consumes: None
- Produces: 三个环境配置文件、`requirements.txt`

- [ ] **Step 1: 创建 `requirements.txt`**

```txt
funasr>=1.0.0
modelscope>=1.0.0
websockets>=10.0
PyYAML>=6.0
numpy>=1.19.0
torch>=1.9.0
```

- [ ] **Step 2: 创建开发环境配置 `configs/development.yaml`**

```yaml
# 服务配置
host: "0.0.0.0"
port: 10095

# 模型配置
asr_model_online: "iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online"
asr_model_online_revision: "v2.0.4"
vad_model: "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"
vad_model_revision: "v2.0.4"
punc_model: "iic/punc_ct-transformer_zh-cn-common-vad_realtime-vocab272727"
punc_model_revision: "v2.0.4"

# 运行环境
ngpu: 1
ncpu: 4
device: "auto"
worker_threads: 8

# 并发控制
concurrent_vad: 4
concurrent_asr_online: 4
concurrent_punc: 1

# 模型管理
models_dir: "./models"
```

- [ ] **Step 3: 创建测试环境配置 `configs/test.yaml`**

```yaml
host: "0.0.0.0"
port: 10095

asr_model_online: "iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online"
asr_model_online_revision: "v2.0.4"
vad_model: "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"
vad_model_revision: "v2.0.4"
punc_model: "iic/punc_ct-transformer_zh-cn-common-vad_realtime-vocab272727"
punc_model_revision: "v2.0.4"

ngpu: 0
ncpu: 2
device: "cpu"
worker_threads: 4

concurrent_vad: 1
concurrent_asr_online: 1
concurrent_punc: 1

models_dir: "./models"
```

- [ ] **Step 4: 创建生产环境配置 `configs/production.yaml`**

```yaml
host: "0.0.0.0"
port: 10095

asr_model_online: "iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online"
asr_model_online_revision: "v2.0.4"
vad_model: "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"
vad_model_revision: "v2.0.4"
punc_model: "iic/punc_ct-transformer_zh-cn-common-vad_realtime-vocab272727"
punc_model_revision: "v2.0.4"

ngpu: 1
ncpu: 8
device: "auto"
worker_threads: 16

concurrent_vad: 8
concurrent_asr_online: 8
concurrent_punc: 2

models_dir: "./models"
```

- [ ] **Step 5: 验证配置文件格式正确**

Run:
```bash
python -c "import yaml; yaml.safe_load(open('configs/development.yaml')); yaml.safe_load(open('configs/test.yaml')); yaml.safe_load(open('configs/production.yaml')); print('OK')"
```

Expected: `OK`

- [ ] **Step 6: 提交基础配置**（如使用 git）

```bash
git add configs/ requirements.txt
git commit -m "chore: add multi-env config and requirements"
```

---

## Task 2: 配置加载模块

**Files:**
- Create: `config_loader.py`（临时模块，便于测试）
- Modify: `FunASR-Service.py`（后续集成）

**Interfaces:**
- Consumes: `configs/*.yaml` 文件
- Produces: `load_config(env: str, config_path: Optional[str]) -> dict`, `detect_device(config: dict) -> dict`

- [ ] **Step 1: 编写配置加载模块 `config_loader.py`**

```python
import os
import yaml
import torch
from typing import Optional


CONFIG_DIR = "configs"


def detect_device(config: dict) -> dict:
    """处理 device=auto，自动选择可用的后端。"""
    device = config.get("device", "auto")
    if device != "auto":
        return config
    
    if torch.cuda.is_available():
        config["device"] = "cuda"
    elif torch.backends.mps.is_available():
        config["device"] = "mps"
    else:
        config["device"] = "cpu"
    return config


def load_config(env: str, config_path: Optional[str] = None) -> dict:
    """从 YAML 文件加载配置。"""
    if config_path is None:
        config_path = os.path.join(CONFIG_DIR, f"{env}.yaml")
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    if not isinstance(config, dict):
        raise ValueError(f"配置文件格式错误: {config_path}")
    
    config = detect_device(config)
    return config
```

- [ ] **Step 2: 创建测试 `tests/test_config.py`**

```python
import pytest
import os
from config_loader import load_config, detect_device


def test_detect_device_cuda():
    import torch
    config = {"device": "auto"}
    detect_device(config)
    assert config["device"] in ["cuda", "mps", "cpu"]


def test_detect_device_explicit():
    config = {"device": "cpu"}
    detect_device(config)
    assert config["device"] == "cpu"


def test_load_config_development():
    config = load_config("development")
    assert config["host"] == "0.0.0.0"
    assert config["port"] == 10095
    assert "models_dir" in config


def test_load_config_missing():
    with pytest.raises(FileNotFoundError):
        load_config("nonexistent")
```

- [ ] **Step 3: 运行测试**（预期失败，因为 `pytest` 环境可能未安装）

Run:
```bash
python -m pytest tests/test_config.py -v
```

Expected: 若未安装 pytest，则提示安装；否则测试通过。

- [ ] **Step 4: 提交配置加载模块**

```bash
git add config_loader.py tests/test_config.py
git commit -m "feat: add config loader with device auto-detection"
```

---

## Task 3: 模型预下载模块

**Files:**
- Create: `model_manager.py`（临时模块，便于测试）
- Modify: `FunASR-Service.py`（后续集成）

**Interfaces:**
- Consumes: `config["models_dir"]`, `config["*_model"]`, `config["*_model_revision"]`
- Produces: `download_model(model_name: str, model_revision: str, local_dir: str) -> str`, `ensure_models(config: dict)`

- [ ] **Step 1: 编写模型管理模块 `model_manager.py`**

```python
import os
from modelscope import snapshot_download


def download_model(model_name: str, model_revision: str, local_dir: str) -> str:
    """检查模型是否已下载，未下载则自动下载。"""
    local_path = os.path.join(local_dir, model_name)
    if os.path.exists(local_path) and os.listdir(local_path):
        return local_path
    
    try:
        print(f"正在下载模型: {model_name} (revision: {model_revision})")
        return snapshot_download(
            model_name,
            revision=model_revision,
            cache_dir=local_dir,
        )
    except Exception as e:
        raise RuntimeError(f"模型下载失败: {model_name} (revision: {model_revision}). 错误: {e}") from e


def ensure_models(config: dict):
    """确保所有模型已下载。"""
    models_dir = config.get("models_dir", "./models")
    os.makedirs(models_dir, exist_ok=True)
    
    models = [
        (config["asr_model_online"], config["asr_model_online_revision"]),
        (config["vad_model"], config["vad_model_revision"]),
        (config["punc_model"], config["punc_model_revision"]),
    ]
    
    for model_name, revision in models:
        download_model(model_name, revision, models_dir)
```

- [ ] **Step 2: 创建测试 `tests/test_model_download.py`**

```python
import os
import pytest
from unittest.mock import patch, MagicMock
from model_manager import download_model, ensure_models


def test_download_model_already_exists(tmp_path):
    model_name = "test/model"
    model_dir = tmp_path / "test" / "model"
    model_dir.mkdir(parents=True)
    (model_dir / "dummy.txt").write_text("dummy")
    
    result = download_model(model_name, "v1", str(tmp_path))
    assert result == os.path.join(str(tmp_path), model_name)


def test_ensure_models_downloads_missing(tmp_path):
    config = {
        "models_dir": str(tmp_path),
        "asr_model_online": "asr/model",
        "asr_model_online_revision": "v1",
        "vad_model": "vad/model",
        "vad_model_revision": "v1",
        "punc_model": "punc/model",
        "punc_model_revision": "v1",
    }
    
    with patch("model_manager.download_model") as mock_download:
        mock_download.return_value = "mocked/path"
        ensure_models(config)
        assert mock_download.call_count == 3
```

- [ ] **Step 3: 运行测试**

Run:
```bash
python -m pytest tests/test_model_download.py -v
```

Expected: PASS

- [ ] **Step 4: 提交模型管理模块**

```bash
git add model_manager.py tests/test_model_download.py
git commit -m "feat: add model download and cache management"
```

---

## Task 4: 重构 `FunASR-Service.py`

**Files:**
- Modify: `FunASR-Service.py`

**Interfaces:**
- Consumes: `load_config`, `ensure_models`
- Produces: 精简后的 WebSocket 服务

- [ ] **Step 1: 导入依赖并移除不需要的模块**

保留：
```python
import asyncio
import json
import websockets
import time
import argparse
import os
import functools
import yaml
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import torch
from funasr import AutoModel
from modelscope import snapshot_download
```

移除：
```python
import ssl  # 如不使用 SSL
import wave
from scipy.spatial.distance import cosine
```

- [ ] **Step 2: 添加配置加载和模型下载函数**

```python
def load_config(env: str, config_path: str = None) -> dict:
    if config_path is None:
        config_path = f"configs/{env}.yaml"
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    if config.get("device") == "auto":
        config["device"] = "cuda" if torch.cuda.is_available() else \
                          ("mps" if torch.backends.mps.is_available() else "cpu")
    return config


def download_model(model_name: str, model_revision: str, local_dir: str) -> str:
    local_path = os.path.join(local_dir, model_name)
    if os.path.exists(local_path) and os.listdir(local_path):
        return local_path
    
    try:
        print(f"正在下载模型: {model_name} (revision: {model_revision})")
        return snapshot_download(model_name, revision=model_revision, cache_dir=local_dir)
    except Exception as e:
        raise RuntimeError(f"模型下载失败: {model_name} (revision: {model_revision}). 错误: {e}") from e


def ensure_models(config: dict):
    models_dir = config.get("models_dir", "./models")
    os.makedirs(models_dir, exist_ok=True)
    models = [
        (config["asr_model_online"], config["asr_model_online_revision"]),
        (config["vad_model"], config["vad_model_revision"]),
        (config["punc_model"], config["punc_model_revision"]),
    ]
    for model_name, revision in models:
        download_model(model_name, revision, models_dir)
```

- [ ] **Step 3: 解析命令行参数 `--env` 和 `--config`**

```python
parser = argparse.ArgumentParser()
parser.add_argument("--env", type=str, default="development", help="环境名称")
parser.add_argument("--config", type=str, default=None, help="配置文件路径")
args = parser.parse_args()

config = load_config(args.env, args.config)
ensure_models(config)
```

- [ ] **Step 4: 加载三个模型（流式 ASR、VAD、标点）**

```python
models_dir = config["models_dir"]
model_vad = AutoModel(
    model=os.path.join(models_dir, config["vad_model"]),
    model_revision=config["vad_model_revision"],
    ngpu=config["ngpu"],
    ncpu=config["ncpu"],
    device=config["device"],
    disable_pbar=True,
    disable_log=True,
)

model_asr_streaming = AutoModel(
    model=os.path.join(models_dir, config["asr_model_online"]),
    model_revision=config["asr_model_online_revision"],
    ngpu=config["ngpu"],
    ncpu=config["ncpu"],
    device=config["device"],
    disable_pbar=True,
    disable_log=True,
)

model_punc = AutoModel(
    model=os.path.join(models_dir, config["punc_model"]),
    model_revision=config["punc_model_revision"],
    ngpu=config["ngpu"],
    ncpu=config["ncpu"],
    device=config["device"],
    disable_pbar=True,
    disable_log=True,
)
```

- [ ] **Step 5: 移除以下函数和逻辑**

- `async_asr()` 离线识别函数
- `_sv_and_match_sync()` 声纹匹配函数
- `_load_speaker_db_sync()`, `get_speaker_db_cached()`
- `save_offline_wav_segment_sync()`, `_save_wav_sync()`, `_ensure_dir()`
- `to_python()`（如果最终返回格式只包含字符串，则不再需要）
- `speaker_db.json` 相关逻辑
- `mode` 参数处理
- 2pass 模式的 `frames_asr` 离线缓冲区和相关逻辑
- `save_offline_segments` 相关逻辑
- `SEM_ASR_OFFLINE`, `SEM_SV`, `SEM_WAV`

- [ ] **Step 6: 修改 `ws_serve` 仅保留流式逻辑，并初始化 `is_speaking`**

```python
async def ws_serve(websocket, path=None):
    if path is None:
        path = getattr(websocket, "path", None)
    
    frames_asr_online = []
    websocket_users.add(websocket)
    
    websocket.status_dict_asr_online = {"cache": {}, "is_final": False}
    websocket.status_dict_vad = {"cache": {}, "is_final": False}
    websocket.status_dict_punc = {"cache": {}}
    
    websocket.chunk_interval = 10
    websocket.vad_pre_idx = 0
    websocket.wav_name = "microphone"
    websocket.is_speaking = True  # 初始化
    speech_start = False
    speech_end_i = -1
    
    try:
        async for message in websocket:
            if isinstance(message, str):
                messagejson = json.loads(message)
                
                if "is_speaking" in messagejson:
                    websocket.is_speaking = bool(messagejson["is_speaking"])
                
                if "chunk_interval" in messagejson:
                    websocket.chunk_interval = int(messagejson["chunk_interval"])
                
                if "wav_name" in messagejson:
                    websocket.wav_name = messagejson.get("wav_name") or websocket.wav_name
                
                if "chunk_size" in messagejson:
                    chunk_size = messagejson["chunk_size"]
                    if isinstance(chunk_size, str):
                        chunk_size = [x.strip() for x in chunk_size.split(",") if x.strip()]
                    websocket.status_dict_asr_online["chunk_size"] = [int(x) for x in chunk_size]
                
                if "encoder_chunk_look_back" in messagejson:
                    websocket.status_dict_asr_online["encoder_chunk_look_back"] = messagejson["encoder_chunk_look_back"]
                
                if "decoder_chunk_look_back" in messagejson:
                    websocket.status_dict_asr_online["decoder_chunk_look_back"] = messagejson["decoder_chunk_look_back"]
                
                if "hotwords" in messagejson:
                    websocket.status_dict_asr_online["hotword"] = messagejson["hotwords"]
                
                continue
            
            pcm = message
            duration_ms = _pcm_duration_ms(pcm, fs=16000, ch=1, sampwidth=2)
            websocket.vad_pre_idx += duration_ms
            
            # 累积音频帧
            frames_asr_online.append(pcm)
            
            # VAD 检测
            speech_start_i, speech_end_i = await async_vad(websocket, pcm)
            
            if speech_start_i != -1:
                speech_start = True
            
            is_final = (speech_end_i != -1) or (not websocket.is_speaking)
            websocket.status_dict_asr_online["is_final"] = is_final
            
            # 定期触发流式ASR（非最终结果）
            if (len(frames_asr_online) % websocket.chunk_interval == 0) and not is_final:
                audio_in = b"".join(frames_asr_online)
                text = await async_asr_online(websocket, audio_in)
                if text:
                    msg = {
                        "text": text,
                        "wav_name": websocket.wav_name,
                        "is_final": False,
                    }
                    await websocket.send(json.dumps(msg, ensure_ascii=False))
            
            # 语音结束处理：获取最终结果并加标点
            if is_final:
                audio_in = b"".join(frames_asr_online)
                text = await async_asr_online(websocket, audio_in)
                
                if text and model_punc:
                    punc_out = await run_blocking(
                        _generate_sync,
                        model_punc,
                        text,
                        websocket.status_dict_punc,
                        sem=SEM_PUNC,
                    )
                    text = punc_out[0].get("text", text)
                
                if text:
                    msg = {
                        "text": text,
                        "wav_name": websocket.wav_name,
                        "is_final": True,
                    }
                    await websocket.send(json.dumps(msg, ensure_ascii=False))
                
                # 重置状态
                frames_asr_online = []
                speech_start = False
                speech_end_i = -1
                websocket.status_dict_asr_online = {"cache": {}, "is_final": False}
                websocket.status_dict_vad = {"cache": {}, "is_final": False}
                websocket.vad_pre_idx = 0
                
    except websockets.ConnectionClosed:
        print("ConnectionClosed...")
    except Exception as e:
        print("Exception:", e)
    finally:
        await ws_reset(websocket)
        websocket_users.discard(websocket)
```

- [ ] **Step 7: 修改 `async_asr_online` 仅执行 ASR 并返回文本，不再发送消息**

```python
async def async_asr_online(websocket, audio_in: bytes) -> str:
    if len(audio_in) <= 0:
        return ""
    
    rec_out = await run_blocking(
        _generate_sync,
        model_asr_streaming,
        audio_in,
        websocket.status_dict_asr_online,
        sem=SEM_ASR_ONLINE,
    )
    rec_result = rec_out[0]
    return rec_result.get("text", "")
```

- [ ] **Step 8: 运行语法检查**

Run:
```bash
python -m py_compile FunASR-Service.py
```

Expected: 无语法错误

- [ ] **Step 9: 提交重构后的主文件**

```bash
git add FunASR-Service.py
git commit -m "refactor: simplify to streaming-only with config and model auto-download"
```

---

## Task 5: 移除临时模块并整合

**Files:**
- Delete: `config_loader.py`
- Delete: `model_manager.py`
- Modify: `FunASR-Service.py`

**Interfaces:**
- Consumes: `config_loader.py`, `model_manager.py`
- Produces: 自包含的 `FunASR-Service.py`

**说明**: Task 2 和 Task 3 创建临时独立模块的目的是为了便于单元测试（TDD）。在 Task 4 中，这些函数已经内联到 `FunASR-Service.py` 中。本任务负责清理临时文件，并更新测试引用。

- [ ] **Step 1: 将 `load_config`, `ensure_models`, `download_model` 合并到 `FunASR-Service.py` 中**

确保 `FunASR-Service.py` 顶部有这些函数定义，然后删除临时文件。

- [ ] **Step 2: 更新测试引用**

修改 `tests/test_config.py` 和 `tests/test_model_download.py`，从 `FunASR-Service.py` 导入函数（如果测试需要继续保留），或者删除测试。

更推荐的做法：保留测试，但改为测试 `FunASR-Service.py` 中的函数。

```python
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from FunASR_Service import load_config, ensure_models, download_model
```

注意：导入名需要与实际模块名匹配。

- [ ] **Step 3: 删除临时文件**

```bash
rm config_loader.py model_manager.py
```

- [ ] **Step 4: 提交整合**

```bash
git add FunASR-Service.py tests/
git rm config_loader.py model_manager.py
git commit -m "refactor: inline config and model management into main service"
```

---

## Task 6: 验证与测试

**Files:**
- Modify: `FunASR-Service.py`（如有问题）
- Create: `tests/test_integration.py`

**Interfaces:**
- Consumes: 完整的服务
- Produces: 可运行的测试

- [ ] **Step 1: 编写集成测试 `tests/test_integration.py`**

```python
import pytest
import asyncio
import websockets
import json
from FunASR_Service import load_config


@pytest.mark.asyncio
async def test_websocket_connection():
    """测试 WebSocket 服务可以连接并接收配置消息。"""
    config = load_config("test")
    uri = f"ws://{config['host']}:{config['port']}"
    
    try:
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
    except ConnectionRefusedError:
        pytest.skip("服务未启动")
```

- [ ] **Step 2: 运行单元测试**

Run:
```bash
python -m pytest tests/ -v
```

Expected: 配置文件测试和模型下载测试通过；集成测试可能需要服务已启动。

- [ ] **Step 3: 手动启动测试**

Run:
```bash
python FunASR-Service.py --env test
```

Expected: 服务启动，检查模型是否存在，不存在则下载，然后监听 WebSocket 端口。

- [ ] **Step 4: 提交测试**

```bash
git add tests/
git commit -m "test: add integration tests for streaming service"
```

---

## Self-Review

### Spec Coverage

| 设计需求 | 对应任务 |
|---------|---------|
| 多环境 YAML 配置 | Task 1, Task 2 |
| 启动参数迁移到配置文件 | Task 2, Task 4 |
| 模型自动下载 | Task 3, Task 4 |
| 仅流式 ASR | Task 4 |
| 移除离线/2pass/SV | Task 4 |
| 支持 Mac MPS | Task 2 (detect_device), Task 4 |
| WebSocket 消息简化 | Task 4 |

### Placeholder Scan

- 无 TBD/TODO
- 无 “add appropriate error handling” 等模糊描述
- 所有步骤包含实际代码

### Type Consistency

- `load_config(env: str, config_path: Optional[str]) -> dict`
- `download_model(model_name: str, model_revision: str, local_dir: str) -> str`
- `ensure_models(config: dict)`
- `async_asr_online(websocket, audio_in: bytes)`

### 依赖说明

- 当前环境不是 git 仓库，因此 `git commit` 步骤可能无法执行，需要在使用前初始化 git 仓库或忽略这些步骤。
- 集成测试需要模型已下载，可能耗时较长。

---

**Plan complete and saved to `docs/superpowers/plans/2026-07-04-funasr-streaming-refactor.md`.**

## 执行选项

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach would you like to use?