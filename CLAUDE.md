# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

这是一个基于 FunASR 的实时语音对话助手系统，整合了：
- **ASR**：使用 DashScope FunASR 进行实时语音识别
- **LLM**：调用 OpenAI API 兼容的大模型进行流式对话
- **TTS**：使用 Qwen3-TTS 进行实时语音合成

完整流程：麦克风录音 → 实时 ASR → LLM 流式回复 → TTS 实时播放

## 项目结构

```
.
├── voice_assistant.py    # 主程序：整合 ASR + LLM + TTS
├── tts_player.py         # TTS 播放器模块（WebSocket 流式播放）
├── requirements.txt      # Python 依赖
├── README.md            # 项目文档
└── docs/superpowers/    # 设计和规划文档
```

**注意**：README.md 中提到的 `FunASR-Service.py`、`FunASR-Client.py` 和 `configs/` 目录在当前版本中不存在，属于旧版本文档。

## 常用命令

### 环境设置

```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境（Windows）
.venv\Scripts\activate

# 激活虚拟环境（Linux/Mac）
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 运行程序

```bash
# 运行语音助手（主程序）
python voice_assistant.py

# 运行 TTS 播放器测试
python tts_player.py
```

### 退出程序

按 `Ctrl+C` 触发优雅退出，会自动清理资源并打印延迟统计。

## 架构说明

### 核心组件关系

```
┌─────────────────────────────────────────────────────────────┐
│                     voice_assistant.py                       │
├─────────────┬──────────────────────┬───────────────────────┤
│   ASR 模块   │      LLM 模块        │       TTS 模块         │
├─────────────┼──────────────────────┼───────────────────────┤
│ DashScope   │  OpenAI API          │   dashscope.qwen_tts   │
│ fun-asr     │  (流式输出)          │   (WebSocket 流式)     │
└─────────────┴──────────────────────┴───────────────────────┘
```

### 关键设计点

1. **单例模式**：
   - `TTSPlayer` 在程序启动时创建一次并常驻，避免每轮对话重连 WebSocket
   - `OpenAI client` 只创建一次并复用

2. **回声消除**：
   - 使用 `is_speaking` Event 在 TTS 播放期间暂停发送麦克风音频
   - 避免外放声音被识别回去造成自问自答

3. **语音检测**：
   - `ENERGY_THRESHOLD = 300`：低于此能量视为环境噪音
   - `SPEECH_HANG_FRAMES = 30`：语音结束后继续发送的帧数，避免截断词尾

4. **TTS 缓冲**：
   - `flush_chars = 20`：字符数达到 20 时触发 flush
   - `flush_interval = 0.15`：距离上次输入超过 150ms 触发 flush
   - 遇到标点符号立即触发 flush

### API 配置

项目使用以下 API（硬编码在 voice_assistant.py 中）：

- **ASR**：DashScope WebSocket (`wss://ws-pfc9xcvzdopof45u.cn-beijing.maas.aliyuncs.com`)
- **LLM**：内部部署的 OpenAI 兼容接口 (`http://192.168.16.10:8080/sourcing/v1`)
- **TTS**：DashScope Qwen3-TTS Realtime

## 开发注意事项

### 模型配置

- LLM 模型：`qwen-turbo`
- ASR 模型：`fun-asr-realtime`
- TTS 模型：`qwen3-tts-flash-realtime`
- TTS 音色：`Cherry`

### 音频参数

- 采样率：`16000`（录音）、`24000`（TTS 输出）
- 块大小：`3200`（约 100ms）
- 格式：`pcm`

### 系统提示词

LLM 被配置为招聘领域专属 AI 助手，仅回答招聘相关问题，非招聘问题会返回固定回复。

### 依赖说明

关键依赖版本：
- `dashscope==1.26.2`：ASR 和 TTS 服务
- `openai==2.44.0`：LLM 调用
- `pyaudio==0.2.14`：麦克风录音
- `sounddevice==0.5.5`：音频播放

### 端口和网络

- 需要连接外部 DashScope 服务（WebSocket）
- 需要连接内部 LLM 服务（HTTP）
