# 语音对话助手系统

基于 [FunASR](https://github.com/alibaba-damo-academy/FunASR) + 大模型 + Qwen3-TTS 的实时语音对话系统，支持网页版和命令行版两种运行模式。

---

## 📋 功能特性

### 网页版 (`web_voice_assistant/`)
- 🌐 **Web 界面**: 现代化响应式设计，支持桌面和移动端
- 🎤 **按住说话**: 按住按钮录音，松开自动识别
- 📡 **实时对话**: ASR → LLM → TTS 全流式处理
- 🔊 **自动播放**: AI 语音实时合成并自动播放
- 💬 **对话展示**: 类似微信的聊天界面，支持流式文字显示

### 命令行版 (`voice_assistant.py`)
- 🎙️ **实时录音**: 使用麦克风实时录制音频
- 🎯 **流式识别**: FunASR 实时语音识别
- 🤖 **AI 对话**: 基于大模型的流式回复
- 🔈 **语音合成**: Qwen3-TTS 实时语音播放

---

## 🏗️ 系统架构

### 网页版架构
```
浏览器 (Web Audio API)
    ↓ WebSocket
FastAPI 服务
    ↓
├─→ DashScope ASR (实时语音识别)
├─→ OpenAI LLM (流式对话生成)
└─→ DashScope TTS (实时语音合成)
```

### 命令行版架构
```
voice_assistant.py
├─→ PyAudio (麦克风录音)
├─→ DashScope ASR (实时语音识别)
├─→ OpenAI LLM (流式对话生成)
└─→ DashScope TTS (实时语音合成)
```

---

## 🚀 快速开始

### 环境准备

**Python 版本**: Python 3.8+

**安装依赖**:

```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境（Windows）
.venv\Scripts\activate

# 激活虚拟环境（Linux/Mac）
source .venv/bin/activate

# 安装基础依赖
pip install -r requirements.txt
```

---

## 📖 使用指南

### 方式一：网页版（推荐）

#### 1. 安装依赖

```bash
cd web_voice_assistant
pip install -r requirements-web.txt
```

#### 2. 启动服务

```bash
python main.py
```

服务启动后将显示：
```
============================================================
语音对话助手服务
============================================================
服务地址: http://localhost:8000
WebSocket: ws://localhost:8000/ws
============================================================
```

#### 3. 访问应用

在浏览器中打开 `http://localhost:8000`

#### 4. 使用步骤

1. **按住说话按钮** - 状态变为"正在听..."
2. **对着麦克风说话** - 实时录音并传输到后端
3. **松开按钮** - 状态变为"思考中..."
4. **等待 AI 回复** - 文字逐字显示，语音自动播放
5. **进行下一轮对话** - 重复步骤 1-4

#### 网页版特性

- **状态指示**: 等待中 → 正在听 → 思考中 → 播放中 → 等待中
- **对话展示**: 用户消息（右侧蓝色）、AI 消息（左侧白色）
- **错误处理**: 麦克风权限、网络连接等错误提示
- **自动重连**: WebSocket 断开自动重连

---

### 方式二：命令行版

#### 启动语音助手

```bash
python voice_assistant.py
```

#### 使用步骤

1. 程序启动后自动开始录音
2. 对着麦克风说话
3. 说完后等待识别结果
4. AI 自动回复并播放语音
5. 可以连续对话

#### 退出程序

按 `Ctrl+C` 触发优雅退出，会自动清理资源并打印延迟统计。

---

## 📁 项目结构

```
.
├── README.md                          # 项目文档
├── requirements.txt                   # 基础依赖
├── CLAUDE.md                          # 开发指南
├── voice_assistant.py                 # 命令行版主程序
├── tts_player.py                      # TTS 播放器模块
│
└── web_voice_assistant/              # 网页版目录
    ├── main.py                        # FastAPI 入口
    ├── websocket_handler.py           # WebSocket 连接处理
    ├── audio_pipeline.py              # ASR/TTS 音频流处理
    ├── chat_manager.py                # LLM 对话管理
    ├── requirements-web.txt           # 网页版依赖
    └── static/                        # 前端静态文件
        ├── index.html                 # 主页面
        ├── style.css                  # 样式文件
        └── app.js                     # 前端逻辑
```

---

## ⚙️ 配置说明

### API 配置

项目使用以下 API（可通过环境变量配置）：

| 服务 | 环境变量 | 默认值 |
|------|---------|--------|
| ASR | `DASHSCOPE_API_KEY` | sk-5161496c3b6a4690b7a6c4a075a74181 |
| LLM | `LLM_API_KEY` | 99161F95-3F04-45AA-831B-B976C8C23293 |
| LLM | `LLM_BASE_URL` | http://192.168.16.10:8080/sourcing/v1 |
| LLM | `LLM_MODEL` | qwen-turbo |

### 音频参数

| 参数 | 录音 | 播放 |
|------|------|------|
| 采样率 | 16000 Hz | 24000 Hz |
| 采样位数 | 16 bit | 16 bit |
| 声道数 | 1 (单声道) | 1 (单声道) |
| 编码格式 | PCM | PCM |

### 系统提示词

LLM 被配置为**招聘领域专属 AI 助手**：
- 仅回答招聘、人力资源、岗位、简历、面试、薪酬福利等相关问题
- 对非招聘领域问题统一回复："抱歉，我只能回答招聘相关的问题。"
- 回复简洁专业，控制在 1-3 句话（不超过 50 字）

---

## 🔧 依赖说明

### 基础依赖 (requirements.txt)
- PyYAML
- numpy
- openai
- sounddevice
- dashscope
- pyaudio

### 网页版额外依赖 (requirements-web.txt)
- fastapi
- uvicorn
- websockets
- python-multipart

---

## 🌐 网络要求

- 需要连接外部 DashScope 服务（WebSocket）
- 需要连接内部 LLM 服务（HTTP）
- 确保网络稳定以获得最佳体验

---

## 📝 注意事项

### 网页版
1. **浏览器要求**: 支持 Web Audio API 的现代浏览器（Chrome、Firefox、Edge、Safari）
2. **麦克风权限**: 首次使用需要允许浏览器访问麦克风
3. **HTTPS**: 在正式环境中建议使用 HTTPS，否则麦克风权限可能被浏览器阻止

### 命令行版
1. **音频设备**: 确保系统有可用的麦克风和扬声器
2. **权限问题**: macOS/Linux 可能需要配置音频权限

---

## 🔮 后续扩展

- [ ] 多用户支持（WebSocket 会话管理）
- [ ] 对话历史持久化（数据库存储）
- [ ] 用户认证（JWT 登录）
- [ ] 音频可视化（录音波形动画）
- [ ] 移动端 PWA 支持
- [ ] 多语言支持

---

## 📄 许可证

本项目基于 FunASR 开源项目，遵循 Apache License 2.0。

---

## 🙏 致谢

- [FunASR](https://github.com/alibaba-damo-academy/FunASR) - 阿里巴巴达摩院开源语音识别 toolkit
- [DashScope](https://www.modelscope.cn/) - 阿里云计算模型服务平台
- [FastAPI](https://fastapi.tiangolo.com/) - 现代 Python Web 框架

---

**最后更新**: 2026-07-10
