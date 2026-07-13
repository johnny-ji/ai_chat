# 网页版语音对话演示系统设计文档

**日期**: 2026-07-10  
**状态**: 已批准  
**作者**: Claude Code

---

## 1. 项目概述

### 1.1 目标
将现有的命令行语音助手改造为网页版演示系统，用户可以通过浏览器访问，按住按钮进行语音对话，AI 回复以文字和语音形式实时呈现。

### 1.2 核心功能
- **按住说话**：按住按钮录音，松开自动识别
- **实时对话**：ASR 识别 → LLM 生成 → TTS 播放全流式处理
- **自动播放**：TTS 音频实时传回浏览器自动播放
- **对话展示**：类似微信聊天的对话界面

### 1.3 技术栈
- **前端**: 原生 HTML + JavaScript + Web Audio API
- **后端**: Python + FastAPI + WebSocket
- **通信**: WebSocket 双向实时流传输

---

## 2. 系统架构

### 2.1 架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              浏览器 (前端)                               │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────────┐   │
│  │ 录音按钮 │───▶│ Web Audio│───▶│ WebSocket │───▶│ 对话展示区   │   │
│  │ (按住)   │    │ 录音 API │    │ 客户端    │    │ (实时更新)   │   │
│  └──────────┘    └──────────┘    └──────────┘    └──────────────┘   │
│                                       │                    ▲         │
│                                       │    PCM 音频        │         │
│                                       └────────────────────┘         │
│                                       │    文本 + 音频流            │
└───────────────────────────────────────┼────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          Python 后端 (FastAPI)                          │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────────┐  │
│  │ WebSocket│───▶│ 音频路由 │───▶│ DashScope│───▶│ LLM 流式    │  │
│  │ 服务端   │    │ 处理器   │    │ ASR      │    │ 生成        │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────────┘  │
│       ▲                              │                    │           │
│       │                              ▼                    ▼           │
│  ┌──────────┐                   ┌──────────┐         ┌──────────┐    │
│  │ TTS 音频 │◀─────────────────│ DashScope│◀────────│ 文本     │    │
│  │ 流输出   │                   │ TTS      │         │ 缓冲     │    │
│  └──────────┘                   └──────────┘         └──────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 组件职责

| 组件 | 职责 |
|-----|------|
| AudioRecorder | Web Audio API 录制麦克风音频 |
| WebSocketClient | WebSocket 连接管理和消息路由 |
| AudioPlayer | Web Audio API 播放 PCM 音频流 |
| ChatUI | 对话界面渲染和状态显示 |
| WebSocketHandler | 后端 WebSocket 连接和消息处理 |
| AudioPipeline | 音频流路由（转发到 ASR、从 TTS 接收） |
| ChatManager | LLM 调用和对话管理 |

---

## 3. 前端设计

### 3.1 页面结构

```html
<div class="chat-container">
  <!-- 对话展示区 -->
  <div class="messages" id="messages"></div>
  
  <!-- 录音按钮区域 -->
  <div class="input-area">
    <div class="status-indicator" id="status">等待中...</div>
    <button class="record-btn" id="recordBtn">按住说话</button>
  </div>
</div>
```

### 3.2 核心 JavaScript 模块

```javascript
// AudioRecorder.js - 录音模块
class AudioRecorder {
  async start() { /* 获取麦克风权限，开始录音 */ }
  stop() { /* 停止录音 */ }
  onData(callback) { /* 定期返回 PCM 数据 */ }
}

// WebSocketClient.js - WebSocket 客户端
class WebSocketClient {
  connect() { /* 建立 WebSocket 连接 */ }
  sendAudio(data) { /* 发送音频数据 */ }
  onMessage(callback) { /* 接收消息 */ }
}

// AudioPlayer.js - 音频播放器
class AudioPlayer {
  play(pcmData) { /* 播放 PCM 音频 */ }
  stop() { /* 停止播放 */ }
}

// ChatUI.js - 对话界面
class ChatUI {
  addUserMessage(text) { /* 添加用户消息 */ }
  addAIMessage(text) { /* 添加 AI 消息 */ }
  updateStatus(state) { /* 更新状态 */ }
}

// StateManager.js - 状态管理
class StateManager {
  transition(from, to) { /* 状态转换 */ }
}
```

### 3.3 交互流程

```
用户按住按钮
    ↓
AudioRecorder.start() → 获取麦克风权限 → 开始录音
    ↓
定期发送 PCM 数据 → WebSocket → 后端
    ↓
用户松开按钮
    ↓
发送"录音结束"信号 → 后端开始 ASR → LLM → TTS
    ↓
接收 AI 文本 → 显示在对话区
接收 TTS 音频 → AudioPlayer.play() → 自动播放
```

---

## 4. 后端设计

### 4.1 项目结构

```
web_voice_assistant/
├── main.py              # FastAPI 入口，启动服务
├── websocket_handler.py # WebSocket 连接和消息路由
├── audio_pipeline.py    # 音频流处理
├── chat_manager.py      # LLM 调用和对话管理
└── static/              # 前端文件
    ├── index.html
    ├── style.css
    └── app.js
```

### 4.2 核心类设计

```python
# websocket_handler.py
class WebSocketHandler:
    """WebSocket 连接管理"""
    async def handle_client(websocket):
        # 1. 接收音频流并转发到 ASR
        # 2. 接收 ASR 结果，触发 LLM
        # 3. 接收 LLM 流式输出，触发 TTS
        # 4. 接收 TTS 音频，发送给前端

# audio_pipeline.py
class AudioPipeline:
    """音频流路由"""
    def forward_to_asr(pcm_data):      # 转发录音到 DashScope ASR
    def receive_from_tts(audio_data):  # 接收 TTS 音频并发送前端

# chat_manager.py
class ChatManager:
    """对话管理"""
    def process_asr_result(text):      # 处理 ASR 识别结果
    async def stream_llm(text):        # 流式调用 LLM
    def trigger_tts(text_chunk):       # 触发 TTS 合成
```

### 4.3 WebSocket 消息协议

**前端 → 后端:**

```json
// 音频数据
{"type": "audio", "data": "base64_encoded_pcm_data"}

// 控制信号
{"type": "control", "action": "start_recording"}
{"type": "control", "action": "stop_recording"}
```

**后端 → 前端:**

```json
// 状态更新
{"type": "status", "state": "listening|thinking|speaking|idle"}

// ASR 识别结果
{"type": "transcription", "text": "识别文本", "is_final": true}

// LLM 流式文本
{"type": "ai_text", "text": "生成的文本片段", "done": false}

// TTS 音频数据
{"type": "audio", "data": "base64_encoded_pcm_data"}

// 本轮结束
{"type": "complete"}
```

---

## 5. 数据流设计

### 5.1 完整时序图

```
时间轴 →

浏览器              后端              DashScope ASR     LLM API          DashScope TTS
  │                  │                    │                │                │
  │──按住按钮────────▶│                    │                │                │
  │                  │──创建 ASR 连接─────▶│                │                │
  │                  │                    │                │                │
  │──PCM 数据────────▶│──转发─────────────▶│                │                │
  │──PCM 数据────────▶│──转发─────────────▶│                │                │
  │   ...            │   ...              │                │                │
  │                  │                    │                │                │
  │──松开按钮────────▶│                    │                │                │
  │                  │──ASR 识别完成──────│                │                │
  │                  │                    │                │                │
  │                  │──调用 LLM ───────────────────────────▶│                │
  │◀──状态: thinking─│                    │                │                │
  │                  │◀─流式文本────────────────────────────│                │
  │                  │                    │                │                │
  │◀──AI 文本片段────│──触发 TTS ───────────────────────────────────────────▶│
  │   (逐字显示)     │                    │                │                │
  │                  │                    │                │                │
  │◀──状态: speaking─│◀──PCM 音频流─────────────────────────────────────────│
  │◀──音频数据───────│                    │                │                │
  │◀──音频数据───────│                    │                │                │
  │   (播放)         │   ...              │                │                │
  │                  │                    │                │                │
  │◀──complete───────│                    │                │                │
  │                  │                    │                │                │
```

### 5.2 关键设计决策

1. **异步管道**：后端使用 `asyncio.Queue` 实现 ASR → LLM → TTS 的无阻塞流水线
2. **音频缓冲**：TTS 生成的音频在后端缓冲 100ms 后发送，避免网络抖动
3. **LLM 文本缓冲**：收集 LLM 输出，按句子或标点触发 TTS，避免频繁调用
4. **Base64 编码**：PCM 数据使用 Base64 编码在 JSON 中传输

---

## 6. 状态机设计

### 6.1 状态转换图

```
                    ┌─────────────┐
                    │   IDLE      │
                    │  (空闲)     │
                    └──────┬──────┘
                           │
                按住按钮    │    松开按钮(无语音)
                           ▼
                    ┌─────────────┐
              ┌────│ RECORDING   │────┐
              │    │  (录音中)   │    │
              │    └─────────────┘    │
         松开按钮│                     │录音失败
              │                     │
              ▼                     ▼
      ┌─────────────┐        ┌─────────────┐
      │RECOGNIZING │        │    ERROR     │
      │  (识别中)  │        │   (错误)     │
      └──────┬──────┘        └─────────────┘
             │                      ▲
             │识别完成              │重试
             ▼                     │
      ┌─────────────┐              │
      │ THINKING   │              │
      │ (LLM思考)  │              │
      └──────┬──────┘              │
             │                     │
             │LLM流式输出          │
             ▼                     │
      ┌─────────────┐              │
      │ SPEAKING   │───────────────┘
      │ (AI说话中) │  错误/完成
      └─────────────┘
             │
             │TTS完成
             ▼
      ┌─────────────┐
      │   IDLE     │
      └─────────────┘
```

### 6.2 状态说明

| 状态 | 说明 | 用户界面 |
|-----|------|---------|
| IDLE | 等待用户操作 | 显示"按住说话" |
| RECORDING | 正在录音 | 按钮高亮，显示波形动画 |
| RECOGNIZING | ASR 识别中 | 显示"识别中..." |
| THINKING | LLM 生成中 | 显示"思考中..." |
| SPEAKING | TTS 播放中 | 显示"播放中..."，AI 消息逐字显示 |
| ERROR | 发生错误 | 显示错误信息和重试按钮 |

---

## 7. 错误处理

### 7.1 错误场景及处理

| 错误场景 | 处理方式 | 用户反馈 |
|---------|---------|---------|
| 麦克风权限拒绝 | 显示权限申请引导 | "请点击允许麦克风权限" |
| WebSocket 断开 | 自动重连（最多3次） | "连接断开，正在重连..." |
| ASR 识别失败 | 返回错误提示，返回 IDLE | "没有听清，请再说一次" |
| LLM API 超时 | 重试3次后提示 | "服务繁忙，请稍后重试" |
| TTS 生成失败 | 仅显示文本，继续对话 | "（仅文本显示）" |

### 7.2 资源清理

- WebSocket 断开时自动停止录音和播放
- 每轮对话结束后重置状态机
- 程序退出时优雅关闭所有连接
- 使用 `try/finally` 确保资源释放

---

## 8. 技术细节

### 8.1 音频参数

| 参数 | 值 | 说明 |
|-----|---|------|
| 采样率 | 16000 Hz | 与 ASR 服务要求一致 |
| 采样位数 | 16 bit | PCM 16位有符号整数 |
| 声道数 | 1 (单声道) | 降低数据量 |
| 块大小 | 3200 samples (~200ms) | 平衡延迟和效率 |
| 编码 | PCM | 无压缩，直接传输 |

### 8.2 WebSocket 配置

| 参数 | 值 | 说明 |
|-----|---|------|
| 路径 | `/ws` | WebSocket 端点 |
| Ping 间隔 | 30s | 保持连接活跃 |
| 消息大小限制 | 100KB | 防止过大消息 |
| 并发连接数 | 50 | 演示环境限制 |

### 8.3 依赖项

```txt
fastapi>=0.100.0
websockets>=11.0
python-multipart>=0.0.6
# 复用现有依赖
dashscope>=1.26.0
openai>=2.44.0
numpy>=1.24.0
```

---

## 9. 实现范围

### 9.1 本期包含 ✅

- [x] WebSocket 实时音频流传输
- [x] DashScope ASR 集成
- [x] LLM 流式对话
- [x] DashScope TTS 实时播放
- [x] 状态机和错误处理
- [x] 响应式 UI 设计
- [x] 麦克风权限处理

### 9.2 后续扩展 ❌

- [ ] 多用户支持
- [ ] 对话历史持久化
- [ ] 用户认证
- [ ] 音频可视化效果增强
- [ ] 多语言支持
- [ ] 移动端优化

---

## 10. 验收标准

1. **功能验收**
   - 按住按钮可录音，松开自动识别
   - AI 回复以文字形式实时显示
   - AI 语音自动播放
   - 一轮对话完成可开始下一轮

2. **性能验收**
   - 首包延迟 < 500ms（录音结束到第一个识别文字）
   - TTS 音频延迟 < 300ms（文字显示到开始播放）
   - 支持连续对话无内存泄漏

3. **稳定性验收**
   - WebSocket 断开后可自动重连
   - 异常情况下优雅降级
   - 无控制台报错

---

## 附录 A: API 配置

使用现有配置：
- **ASR**: DashScope WebSocket (`wss://ws-pfc9xcvzdopof45u.cn-beijing.maas.aliyuncs.com`)
- **LLM**: 内部部署的 OpenAI 兼容接口 (`http://192.168.16.10:8080/sourcing/v1`)
- **TTS**: DashScope Qwen3-TTS Realtime

---

*文档版本: 1.0*  
*最后更新: 2026-07-10*
