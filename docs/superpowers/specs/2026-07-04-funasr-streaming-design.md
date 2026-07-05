# FunASR 流式语音识别服务重构设计

**日期**: 2026-07-04  
**目标**: 将 FunASR-Service.py 精简为仅支持流式语音输入，移除无用代码，并支持 Mac M 系列 CPU  
**作者**: Claude Code

---

## 1. 需求概览

### 1.1 核心需求
- 仅支持流式语音输入（移除离线/2pass 模式）
- 保留 VAD 检测语音结束
- 保留标点符号功能
- 支持 Mac M 系列芯片 (MPS 后端)
- 代码精简 50%+
- 通过配置文件管理多环境（开发/测试/生产）
- 启动时自动检查并下载模型

### 1.2 保留 vs 移除

| 保留功能 | 移除功能 |
|---------|---------|
| WebSocket 流式音频接收 | 离线 ASR 模型 |
| VAD 语音活动检测 | 2pass 模式逻辑 |
| 流式 ASR 实时识别 | 声纹识别 (SV) |
| 标点符号添加 | 音频保存调试 |
| Mac MPS / CUDA / CPU 支持 | 说话人数据库 |
| 多环境配置文件 | `mode` 参数 |
| 模型自动下载 | 命令行启动参数 |

---

## 2. 架构设计

### 2.1 系统架构

```
┌─────────────┐     WebSocket      ┌─────────────────────────────────────────┐
│   客户端    │ ◄────────────────► │           服务端 (asyncio)            │
│ (音频流输入) │                    │                                         │
└─────────────┘                    │  ┌─────────┐   ┌─────────┐   ┌──────┐ │
                                   │  │  VAD    │ → │流式ASR  │ → │ 标点 │ │
                                   │  │ (线程池)│   │ (线程池)│   │(线程池)│ │
                                   │  └─────────┘   └─────────┘   └──────┘ │
                                   │       ↑                              │
                                   │       └─ 检测语音结束触发最终结果    │
                                   └─────────────────────────────────────────┘
```

### 2.2 数据流

**实时流式阶段**（语音进行中）：
```
音频帧 → VAD检测 → 流式ASR → 返回部分识别结果（无标点）
```

**语音结束阶段**（VAD检测到结束或客户端关闭）：
```
当前缓冲区 → 流式ASR(final) → 标点模型 → 返回最终结果（带标点）
```

---

## 3. 代码变更清单

### 3.1 移除的模型

```python
# 删除以下模型加载
- model_asr (离线ASR)
- model_sv (声纹识别)
```

### 3.2 移除的全局变量和配置

```python
# 移除参数
- 所有命令行参数改为配置文件管理
- --asr_model / --asr_model_revision
- --concurrent_asr_offline
- --concurrent_sv
- --speaker_db_reload_sec
- --save_offline_segments
- --save_offline_segments_dir

# 移除全局变量
- SPEAKER_DB_PATH
- _SPEAKER_DB_CACHE
- _SPEAKER_DB_CACHE_TS
- SEM_ASR_OFFLINE
- SEM_SV
- SEM_WAV
```

### 3.3 移除的函数

```python
# 声纹识别相关
- _load_speaker_db_sync()
- get_speaker_db_cached()
- _sv_and_match_sync()

# 音频保存相关
- _ensure_dir()
- _save_wav_sync()
- save_offline_wav_segment_sync()

# 离线ASR相关
- async_asr()
```

### 3.4 移除的 WebSocket 状态

```python
# 从 websocket 对象中移除
- status_dict_asr (离线ASR状态)
- frames_asr (离线音频缓冲区)
- save_offline_segments
- offline_seg_idx
- offline_save_dir
- audio_fs (移到全局或使用固定值)
```

### 3.5 移除的消息字段

**客户端发送（不再支持）：**
```json
{
  "mode": "2pass|online|offline"  // 不再支持
}
```

**服务端返回（不再包含）：**
```json
{
  "mode": "...",          // 移除
  "spk_name": "...",      // 移除
  "spk_score": 0.0,       // 移除
  "timestamp": [...],     // 移除
  "sentence_info": [...], // 移除
  "punc_array": [...]     // 移除
}
```

**精简后的返回格式：**
```json
{
  "text": "识别结果文本",
  "wav_name": "会话标识",
  "is_final": true/false
}
```

---

## 4. 保留功能详述

### 4.1 配置文件参数

所有配置项从配置文件读取，不再通过命令行参数传入：

```yaml
# 服务配置
host: "0.0.0.0"              # 服务地址
port: 10095                  # 服务端口

# 模型配置
asr_model_online: "iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online"
asr_model_online_revision: "v2.0.4"
vad_model: "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"
vad_model_revision: "v2.0.4"
punc_model: "iic/punc_ct-transformer_zh-cn-common-vad_realtime-vocab272727"
punc_model_revision: "v2.0.4"

# 运行环境
ngpu: 1                      # 0=CPU, 1=GPU
ncpu: 4                      # CPU核心数
device: "auto"               # auto / cuda / mps / cpu
worker_threads: 8            # 线程池大小

# 并发控制
concurrent_vad: 4            # VAD并发数
concurrent_asr_online: 4       # 流式ASR并发数
concurrent_punc: 1             # 标点并发数

# 模型管理
models_dir: "./models"       # 本地模型存放目录
```

### 4.2 命令行参数

```python
--env                       # 环境名称: development | test | production
--config                    # （可选）指定配置文件路径
```

### 4.3 设备自动检测逻辑

```python
if config.get("device") == "auto":
    if torch.cuda.is_available():
        config["device"] = "cuda"
    elif torch.backends.mps.is_available():
        config["device"] = "mps"
    else:
        config["device"] = "cpu"
```

### 4.4 保留的 WebSocket 消息

**客户端 → 服务端（文本配置）：**
```json
{
  "is_speaking": true/false,      // 控制是否继续接收
  "chunk_interval": 10,           // 分块间隔
  "wav_name": "session_id",       // 会话标识
  "chunk_size": [5, 10, 5],       // ASR块大小
  "encoder_chunk_look_back": 4,
  "decoder_chunk_look_back": 1,
  "hotwords": "热词1 热词2",      // 热词
  "audio_fs": 16000               // 采样率
}
```

**客户端 → 服务端（二进制音频）：**
- PCM16 little-endian 格式
- 单声道
- 16kHz 采样率（默认）

---

## 5. 环境配置与模型管理

### 5.1 多环境配置文件

采用 YAML 配置文件管理不同环境的参数，统一放置在 `configs/` 目录下：

```
ai_chat/
├── FunASR-Service.py
├── configs/
│   ├── development.yaml
│   ├── test.yaml
│   └── production.yaml
├── models/          # 本地模型存放目录
│   ├── iic/speech_fsmn_vad_zh-cn-16k-common-pytorch/
│   ├── iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online/
│   └── iic/punc_ct-transformer_zh-cn-common-vad_realtime-vocab272727/
```

### 5.2 配置文件示例

**`configs/development.yaml`:**

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
device: "auto"        # 支持: auto / cuda / mps / cpu
worker_threads: 8

# 并发控制
concurrent_vad: 4
concurrent_asr_online: 4
concurrent_punc: 1

# 模型下载
models_dir: "./models"
```

**`configs/production.yaml`:**

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

### 5.3 启动方式

服务启动时仅指定环境名称：

```bash
# 开发环境
python FunASR-Service.py --env development

# 测试环境
python FunASR-Service.py --env test

# 生产环境
python FunASR-Service.py --env production

# 或者显式指定配置文件路径（可选）
python FunASR-Service.py --config configs/development.yaml
```

### 5.4 配置加载逻辑

```python
import yaml
import argparse

def load_config(env: str, config_path: str = None) -> dict:
    """加载配置文件"""
    if config_path is None:
        config_path = f"configs/{env}.yaml"
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    # 处理 "auto" 设备选择
    if config.get("device") == "auto":
        if torch.cuda.is_available():
            config["device"] = "cuda"
        elif torch.backends.mps.is_available():
            config["device"] = "mps"
        else:
            config["device"] = "cpu"
    
    return config
```

### 5.5 模型预下载机制

启动服务前，需要先检查所有模型是否已下载到 `models/` 目录。未下载则自动下载。

```python
import os
from modelscope import snapshot_download

def download_model(model_name: str, model_revision: str, local_dir: str) -> str:
    """下载模型到本地目录"""
    local_path = os.path.join(local_dir, model_name)
    if os.path.exists(local_path) and os.listdir(local_path):
        return local_path
    
    print(f"正在下载模型: {model_name} (revision: {model_revision})")
    return snapshot_download(
        model_name,
        revision=model_revision,
        cache_dir=local_dir,
    )

def ensure_models(config: dict):
    """确保所有模型已下载"""
    models_dir = config.get("models_dir", "./models")
    models = [
        (config["asr_model_online"], config["asr_model_online_revision"]),
        (config["vad_model"], config["vad_model_revision"]),
        (config["punc_model"], config["punc_model_revision"]),
    ]
    
    for model_name, revision in models:
        download_model(model_name, revision, models_dir)
```

### 5.6 模型加载策略

使用本地模型路径加载，避免运行时从网络下载：

```python
# 自动检测本地模型路径
models_dir = config["models_dir"]
model_vad_path = os.path.join(models_dir, config["vad_model"])
model_asr_online_path = os.path.join(models_dir, config["asr_model_online"])
model_punc_path = os.path.join(models_dir, config["punc_model"])

model_vad = AutoModel(
    model=model_vad_path,
    ngpu=config["ngpu"],
    ncpu=config["ncpu"],
    device=config["device"],
    disable_pbar=True,
    disable_log=True,
)
```

### 5.7 依赖更新

需要新增 PyYAML 依赖：

```txt
PyYAML>=6.0
modelscope>=1.0.0
```

---

## 6. 核心逻辑流程

### 6.1 WebSocket 连接处理

```python
async def ws_serve(websocket):
    # 初始化状态
    - frames_asr_online = []  # 流式音频缓冲区
    - status_dict_asr_online = {"cache": {}, "is_final": False}
    - status_dict_vad = {"cache": {}, "is_final": False}
    - status_dict_punc = {"cache": {}}
    
    # 配置
    - wav_name = "microphone"
    - chunk_interval = 10
    - vad_pre_idx = 0
    - speech_start = False
    - speech_end_i = -1
```

### 6.2 音频处理流程

```python
async for message in websocket:
    if isinstance(message, str):
        # 处理配置消息
        handle_config(message)
    else:
        # 处理音频数据
        pcm = message
        frames_asr_online.append(pcm)
        
        # VAD 检测
        speech_start_i, speech_end_i = await async_vad(websocket, pcm)
        
        if speech_start_i != -1:
            speech_start = True
        
        # 流式 ASR（定期或结束时触发）
        if should_trigger_asr():
            await async_asr_online(websocket, audio_in)
        
        # 语音结束处理
        if speech_end_i != -1:
            await async_asr_online_final(websocket, audio_in)
            await add_punctuation_and_send(websocket, text)
            reset_state()
```

### 6.3 线程池和并发控制

```python
EXECUTOR = ThreadPoolExecutor(max_workers=args.worker_threads)
SEM_VAD = asyncio.Semaphore(args.concurrent_vad)
SEM_ASR_ONLINE = asyncio.Semaphore(args.concurrent_asr_online)
SEM_PUNC = asyncio.Semaphore(args.concurrent_punc)

async def run_blocking(fn, *a, sem=None, **kw):
    """在线程池中执行阻塞操作，避免阻塞事件循环"""
    loop = asyncio.get_running_loop()
    call = functools.partial(fn, *a, **kw)
    if sem is None:
        return await loop.run_in_executor(EXECUTOR, call)
    async with sem:
        return await loop.run_in_executor(EXECUTOR, call)
```

---

## 7. 代码结构

### 7.1 精简后的文件结构

```python
# 导入
import asyncio, json, websockets, time, numpy as np, argparse, os, functools
from concurrent.futures import ThreadPoolExecutor
import yaml
import torch
from funasr import AutoModel
from modelscope import snapshot_download

# 配置加载
class AppConfig: ...
def load_config(env): ...
def ensure_models(config): ...

# 工具函数
def to_python(obj): ...
def _pcm_duration_ms(pcm, fs, ch, sampwidth): ...
def _safe_int(v, default): ...

# 线程池和并发控制
EXECUTOR = ...
SEM_VAD, SEM_ASR_ONLINE, SEM_PUNC = ...
async def run_blocking(fn, *a, sem=None, **kw): ...

# 模型加载（3个模型）
model_asr_streaming = ...
model_vad = ...
model_punc = ...

# WebSocket 处理
async def ws_serve(websocket, path=None): ...
async def ws_reset(websocket): ...
async def async_vad(websocket, audio_in): ...
async def async_asr_online(websocket, audio_in): ...

# 主函数
async def main(): ...
if __name__ == "__main__": ...
```

### 7.2 预期代码行数

| 项目 | 行数 |
|------|------|
| 原文件 | ~750 行 |
| 精简后 | ~400 行 |
| 减少 | ~47% |

---

## 8. 测试要点

### 8.1 功能测试

- [ ] WebSocket 连接建立
- [ ] 配置消息解析（chunk_size, hotwords 等）
- [ ] 音频流接收和处理
- [ ] VAD 正确检测语音开始/结束
- [ ] 流式 ASR 返回中间结果
- [ ] 标点符号正确添加
- [ ] 语音结束触发最终结果
- [ ] 多客户端并发处理

### 8.2 环境配置测试

- [ ] 开发/测试/生产配置文件能正常加载
- [ ] 启动参数 `--env` 生效
- [ ] 启动参数 `--config` 可指定自定义路径
- [ ] `device: auto` 能正确选择 cuda/mps/cpu
- [ ] 各环境参数正确隔离

### 8.3 模型下载测试

- [ ] 首次启动自动下载缺失模型
- [ ] 模型已存在时不重复下载
- [ ] 模型目录可自定义配置
- [ ] 下载失败时有明确错误提示

### 8.4 平台测试

- [ ] CUDA (Linux/NVIDIA GPU)
- [ ] MPS (Mac M1/M2/M3)
- [ ] CPU (所有平台)

### 8.5 边界测试

- [ ] 空音频/短音频处理
- [ ] 客户端异常断开
- [ ] 高频并发请求
- [ ] 热词功能正常工作

---

## 9. 兼容性说明

### 9.1 破坏性变更

1. **移除 `mode` 参数**：客户端不再需要发送 `mode`
2. **简化返回格式**：不再包含 `spk_name`, `spk_score`, `timestamp`, `sentence_info`
3. **移除离线功能**：不再支持完整的音频文件识别
4. **启动方式变更**：从命令行参数改为配置文件 + `--env`

### 9.2 客户端适配建议

```javascript
// 旧代码
ws.send(JSON.stringify({mode: "2pass", is_speaking: true}));

// 新代码（简化）
ws.send(JSON.stringify({is_speaking: true}));

// 处理返回（新格式）
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log(data.text);      // 识别文本
    console.log(data.is_final);  // 是否最终结果
};
```

---

## 10. 后续扩展建议

如需在未来添加功能，可考虑：

1. **说话人识别恢复**：重新引入 SV 模型和 `spk_name` 字段
2. **多语言支持**：配置不同的 ASR 模型
3. **实时翻译**：在识别后增加翻译模块
4. **语音合成**：添加 TTS 返回功能

---

## 11. 审批记录

| 版本 | 日期 | 变更内容 | 审批人 |
|------|------|---------|--------|
| v1.0 | 2026-07-04 | 初始设计 | - |

---

**状态**: ⏳ 等待审批  
**下一步**: 用户确认后创建实现计划
