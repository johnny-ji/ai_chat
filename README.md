# FunASR 实时流式语音识别系统

基于 [FunASR](https://github.com/alibaba-damo-academy/FunASR) 的实时流式语音识别系统，包含服务端和客户端，支持多环境配置、模型自动下载和跨平台运行。

---

## 📋 目录

- [功能特性](#功能特性)
- [系统架构](#系统架构)
- [快速开始](#快速开始)
- [服务端使用指南](#服务端使用指南)
- [客户端使用指南](#客户端使用指南)
- [配置说明](#配置说明)
- [开发指南](#开发指南)
- [测试](#测试)
- [常见问题](#常见问题)

---

## ✨ 功能特性

### 服务端 (FunASR-Service.py)

- 🎯 **纯流式识别**：仅支持流式语音输入，实时返回识别结果
- 🔧 **多环境配置**：支持开发/测试/生产环境配置切换
- 📦 **模型自动下载**：启动时自动检查并下载缺失模型
- 🖥️ **跨平台支持**：支持 NVIDIA GPU、Mac M 系列 (MPS)、CPU
- 🔄 **异步处理**：使用 asyncio + ThreadPoolExecutor 实现高并发
- 🔇 **智能断句**：VAD 自动检测语音开始/结束

### 客户端 (FunASR-Client.py)

- 🎤 **实时录音**：使用 `sounddevice` 跨平台录制麦克风
- 📡 **实时传输**：WebSocket 流式发送音频数据
- 📺 **实时显示**：终端实时显示识别结果（中间结果 + 最终结果）
- 💾 **结果保存**：自动保存识别结果到本地文件
- ⌨️ **优雅退出**：Ctrl+C 结束录音并保存结果

---

## 🏗️ 系统架构

```
┌─────────────────┐         WebSocket          ┌──────────────────┐
│   FunASR-Client │  ───────────────────────►  │   FunASR-Service │
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

---

## 🚀 快速开始

### 1. 环境准备

**Python 版本要求**: Python 3.8+

**安装依赖**:

```bash
# 创建虚拟环境（推荐）
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

**系统依赖**:

- **macOS**: 通常无需额外依赖
- **Linux**: 可能需要安装 `portaudio19-dev`
  ```bash
  sudo apt-get install portaudio19-dev  # Debian/Ubuntu
  sudo yum install portaudio-devel       # CentOS/RHEL
  ```
- **Windows**: 通常无需额外依赖

### 2. 启动服务端

```bash
# 开发环境（默认）
python FunASR-Service.py --env development

# 测试环境
python FunASR-Service.py --env test

# 生产环境
python FunASR-Service.py --env production

# 或指定配置文件路径
python FunASR-Service.py --config configs/custom.yaml
```

首次启动会自动下载模型到 `models/` 目录。

### 3. 启动客户端

```bash
# 连接到本地服务端
python FunASR-Client.py --host 127.0.0.1 --port 10095

# 连接到远程服务端
python FunASR-Client.py --host 192.168.1.100 --port 10095
```

说话后，终端将实时显示识别结果，结果自动保存到 `outputs/` 目录。

---

## 📖 服务端使用指南

### 命令行参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--env` | str | `development` | 环境名称（development/test/production） |
| `--config` | str | `None` | 配置文件路径（可选） |

### 支持的模型

| 模型 | 用途 | 默认模型名称 |
|------|------|-------------|
| VAD | 语音活动检测 | `iic/speech_fsmn_vad_zh-cn-16k-common-pytorch` |
| ASR | 流式语音识别 | `iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online` |
| PUNC | 标点符号添加 | `iic/punc_ct-transformer_zh-cn-common-vad_realtime-vocab272727` |

### 输出格式

服务端返回 JSON 格式：

```json
{
  "text": "识别结果文本",
  "wav_name": "microphone",
  "is_final": true
}
```

- `is_final: false` - 中间识别结果
- `is_final: true` - 最终识别结果（语音段结束）

---

## 📱 客户端使用指南

### 命令行参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--host` | str | `127.0.0.1` | 服务端地址 |
| `--port` | int | `10095` | 服务端端口 |

### 使用示例

```bash
# 连接到本地服务端
python FunASR-Client.py --host 127.0.0.1 --port 10095

# 输出示例：
# Connecting to ws://127.0.0.1:10095...
# Connected.
# Start speaking... (Press Ctrl+C to stop)
# Results will be saved to: outputs/FunASR_20250704_120000.txt
# [partial] 你好
# [partial] 你好世界
# [final] 你好世界！
```

### 结果保存

识别结果自动保存到 `outputs/FunASR_<timestamp>.txt`，格式如下：

```
[2025-07-04 12:00:05] 你好世界！
[2025-07-04 12:00:10] 这是一段测试语音。
```

---

## ⚙️ 配置说明

### 配置文件结构

配置文件位于 `configs/` 目录，使用 YAML 格式：

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
ngpu: 1                      # 0=CPU, 1=GPU
ncpu: 4                      # CPU核心数
device: "auto"               # auto/cuda/mps/cpu
worker_threads: 8            # 线程池大小

# 并发控制
concurrent_vad: 4
concurrent_asr_online: 4
concurrent_punc: 1

# 模型管理
models_dir: "./models"
```

### 环境配置对比

| 配置项 | Development | Test | Production |
|--------|-------------|------|------------|
| ngpu | 1 | 0 | 1 |
| ncpu | 4 | 2 | 8 |
| device | auto | cpu | auto |
| worker_threads | 8 | 4 | 16 |
| concurrent_vad | 4 | 1 | 8 |
| concurrent_asr_online | 4 | 1 | 8 |

---

## 🛠️ 开发指南

### 项目结构

```
.
├── FunASR-Service.py          # 服务端主程序
├── FunASR-Client.py           # 客户端主程序
├── config_loader.py           # 配置加载模块
├── model_manager.py           # 模型下载模块
├── requirements.txt           # Python依赖
├── configs/                   # 配置文件目录
│   ├── development.yaml       # 开发环境配置
│   ├── test.yaml              # 测试环境配置
│   └── production.yaml        # 生产环境配置
├── tests/                     # 测试目录
│   ├── test_config.py         # 配置加载测试
│   ├── test_model_download.py # 模型下载测试
│   ├── test_client.py         # 客户端测试
│   └── test_integration.py    # 集成测试
├── models/                    # 模型存放目录（自动创建）
└── outputs/                   # 客户端结果保存目录（自动创建）
```

### 核心模块

#### MicrophoneStream（客户端）

封装 `sounddevice` 录音功能：

```python
async with MicrophoneStream() as stream:
    while True:
        audio_data = await stream.read()
        # 处理音频数据
```

#### load_config（服务端）

加载 YAML 配置并自动检测设备：

```python
config = load_config("development")  # 自动选择 cuda/mps/cpu
```

#### ensure_models（服务端）

检查并下载缺失模型：

```python
ensure_models(config)  # 自动下载到 models/ 目录
```

---

## 🧪 测试

### 运行所有测试

```bash
python -m pytest tests/ -v
```

### 测试覆盖

- ✅ 配置加载测试 (`test_config.py`)
- ✅ 模型下载测试 (`test_model_download.py`)
- ✅ 客户端功能测试 (`test_client.py`)
- ✅ 集成测试 (`test_integration.py`)

### 手动测试

**1. 启动服务端：**
```bash
python FunASR-Service.py --env development
```

**2. 启动客户端：**
```bash
python FunASR-Client.py --host 127.0.0.1 --port 10095
```

**3. 说话测试：**
- 对着麦克风说话
- 观察终端实时输出
- 检查 `outputs/` 目录下的结果文件

---

## ❓ 常见问题

### Q: 启动服务端时提示模型下载失败？

**A:** 检查网络连接，模型会从 ModelScope 下载。如在中国大陆，可能需要配置镜像源：

```bash
export MODELSCOPE_CACHE=./models
```

### Q: 客户端无法连接服务端？

**A:** 
1. 确认服务端已启动：`lsof -i :10095`
2. 检查防火墙设置
3. 确认 host 和 port 参数正确

### Q: 客户端提示没有录音设备？

**A:**
1. **macOS**: 检查系统偏好设置 → 安全性与隐私 → 麦克风权限
2. **Linux**: 检查 `arecord -l` 是否有设备
3. **Windows**: 检查隐私设置 → 麦克风

### Q: 如何切换麦克风设备？

**A:** 修改 `FunASR-Client.py` 中的录音参数，或使用系统默认设备设置。

### Q: 如何支持英文识别？

**A:** 修改配置文件中的模型名称，使用英文 ASR 模型。

### Q: 识别准确率不高？

**A:**
1. 确保麦克风质量良好
2. 调整录音音量（不要太小也不要爆音）
3. 在安静环境下使用
4. 可以尝试添加热词：`{"hotwords": "自定义词"}`

---

## 📄 许可证

本项目基于 FunASR 开源项目，遵循 Apache License 2.0。

---

## 🙏 致谢

- [FunASR](https://github.com/alibaba-damo-academy/FunASR) - 阿里巴巴达摩院开源语音识别 toolkit
- [ModelScope](https://www.modelscope.cn/) - 模型托管平台
- [sounddevice](https://python-sounddevice.readthedocs.io/) - Python 音频录制库

---

## 📧 联系方式

如有问题或建议，欢迎提交 Issue。

---

**最后更新**: 2026-07-04
