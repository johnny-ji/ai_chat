# 网页版语音对话演示系统实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有命令行语音助手改造为网页版演示系统，支持按住按钮录音、实时语音识别、LLM 对话和 TTS 语音播放。

**Architecture:** 采用 FastAPI + WebSocket 架构，前端使用原生 HTML/JS + Web Audio API，后端复用现有 DashScope ASR/LLM/TTS 能力，通过 WebSocket 实现音频和文本的实时流传输。

**Tech Stack:** FastAPI, WebSocket, Web Audio API, DashScope, OpenAI SDK

---

## 项目结构

```
web_voice_assistant/
├── main.py                 # FastAPI 入口
├── websocket_handler.py    # WebSocket 连接处理
├── audio_pipeline.py     # 音频流路由
├── chat_manager.py        # 对话和 LLM 管理
├── requirements-web.txt   # 新增依赖
└── static/
    ├── index.html         # 主页面
    ├── style.css          # 样式
    └── app.js             # 前端逻辑
```

---

## Task 1: 创建项目目录结构

**Files:**
- Create: `web_voice_assistant/`
- Create: `web_voice_assistant/static/`

- [ ] **Step 1: 创建项目目录**

```bash
mkdir -p web_voice_assistant/static
```

- [ ] **Step 2: 提交目录结构**

```bash
git add web_voice_assistant/
git commit -m "chore: create web voice assistant project structure"
```

---

## Task 2: 编写前端 HTML 页面

**Files:**
- Create: `web_voice_assistant/static/index.html`

- [ ] **Step 1: 编写 index.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>语音对话助手</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <div class="container">
        <header class="header">
            <h1>🎙️ 语音对话助手</h1>
            <div class="status" id="status">等待中...</div>
        </header>
        
        <main class="chat-container">
            <div class="messages" id="messages">
                <!-- 对话消息将在这里显示 -->
            </div>
        </main>
        
        <footer class="input-area">
            <button class="record-btn" id="recordBtn">
                <span class="btn-text">按住说话</span>
                <span class="btn-icon">🎤</span>
            </button>
            <p class="hint">按住按钮开始录音，松开结束</p>
        </footer>
    </div>
    
    <script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: 提交 HTML 文件**

```bash
git add web_voice_assistant/static/index.html
git commit -m "feat: add web voice assistant html page"
```

---

## Task 3: 编写前端 CSS 样式

**Files:**
- Create: `web_voice_assistant/static/style.css`

- [ ] **Step 1: 编写 style.css**

```css
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    height: 100vh;
    display: flex;
    justify-content: center;
    align-items: center;
}

.container {
    width: 100%;
    max-width: 600px;
    height: 90vh;
    background: white;
    border-radius: 20px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 20px;
    text-align: center;
}

.header h1 {
    font-size: 24px;
    margin-bottom: 8px;
}

.status {
    font-size: 14px;
    opacity: 0.9;
    padding: 4px 12px;
    border-radius: 12px;
    background: rgba(255, 255, 255, 0.2);
    display: inline-block;
}

.status.recording {
    background: #ff4757;
    animation: pulse 1s infinite;
}

.status.thinking {
    background: #ffa502;
}

.status.speaking {
    background: #2ed573;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.7; }
}

.chat-container {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
    background: #f8f9fa;
}

.messages {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.message {
    max-width: 80%;
    padding: 12px 16px;
    border-radius: 18px;
    word-wrap: break-word;
    animation: slideIn 0.3s ease;
}

@keyframes slideIn {
    from {
        opacity: 0;
        transform: translateY(10px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.message.user {
    align-self: flex-end;
    background: #667eea;
    color: white;
    border-bottom-right-radius: 4px;
}

.message.ai {
    align-self: flex-start;
    background: white;
    color: #333;
    border-bottom-left-radius: 4px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.message.ai.loading {
    color: #999;
}

.input-area {
    padding: 20px;
    background: white;
    border-top: 1px solid #e0e0e0;
    text-align: center;
}

.record-btn {
    width: 80px;
    height: 80px;
    border-radius: 50%;
    border: none;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    font-size: 24px;
    cursor: pointer;
    transition: all 0.3s ease;
    box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    margin: 0 auto;
}

.record-btn:hover {
    transform: scale(1.05);
    box-shadow: 0 6px 20px rgba(102, 126, 234, 0.5);
}

.record-btn:active,
.record-btn.recording {
    transform: scale(0.95);
    background: #ff4757;
    box-shadow: 0 4px 15px rgba(255, 71, 87, 0.4);
}

.record-btn .btn-text {
    font-size: 12px;
    margin-top: 4px;
}

.record-btn .btn-icon {
    font-size: 28px;
}

.hint {
    margin-top: 12px;
    color: #999;
    font-size: 14px;
}

/* 移动端适配 */
@media (max-width: 600px) {
    .container {
        height: 100vh;
        border-radius: 0;
    }
    
    body {
        background: white;
    }
}
```

- [ ] **Step 2: 提交 CSS 文件**

```bash
git add web_voice_assistant/static/style.css
git commit -m "feat: add web voice assistant styles"
```

---

## Task 4: 编写前端 JavaScript - AudioRecorder 模块

**Files:**
- Create: `web_voice_assistant/static/app.js`

- [ ] **Step 1: 编写 AudioRecorder 类**

```javascript
/**
 * AudioRecorder - Web Audio API 录音模块
 * 负责获取麦克风权限并录制音频
 */
class AudioRecorder {
    constructor() {
        this.mediaRecorder = null;
        this.audioContext = null;
        this.source = null;
        this.processor = null;
        this.stream = null;
        this.isRecording = false;
        this.onDataCallback = null;
    }

    /**
     * 开始录音
     * @returns {Promise<void>}
     */
    async start() {
        if (this.isRecording) return;

        try {
            // 获取麦克风权限
            this.stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: 16000,
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true
                }
            });

            // 创建 AudioContext
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: 16000
            });

            // 创建音频源
            this.source = this.audioContext.createMediaStreamSource(this.stream);

            // 创建脚本处理器（用于获取原始 PCM 数据）
            const bufferSize = 2048;
            this.processor = this.audioContext.createScriptProcessor(bufferSize, 1, 1);

            // 处理音频数据
            this.processor.onaudioprocess = (event) => {
                if (!this.isRecording) return;
                
                const inputData = event.inputBuffer.getChannelData(0);
                // 转换为 16-bit PCM
                const pcmData = this.floatTo16BitPCM(inputData);
                
                if (this.onDataCallback) {
                    this.onDataCallback(pcmData);
                }
            };

            // 连接节点
            this.source.connect(this.processor);
            this.processor.connect(this.audioContext.destination);

            this.isRecording = true;
            console.log('[AudioRecorder] 开始录音');

        } catch (error) {
            console.error('[AudioRecorder] 录音失败:', error);
            throw error;
        }
    }

    /**
     * 停止录音
     */
    stop() {
        if (!this.isRecording) return;

        this.isRecording = false;

        // 断开连接
        if (this.processor) {
            this.processor.disconnect();
            this.processor = null;
        }

        if (this.source) {
            this.source.disconnect();
            this.source = null;
        }

        // 关闭 AudioContext
        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }

        // 停止麦克风流
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }

        console.log('[AudioRecorder] 停止录音');
    }

    /**
     * 设置数据回调
     * @param {Function} callback - 回调函数，接收 Uint8Array 类型的 PCM 数据
     */
    onData(callback) {
        this.onDataCallback = callback;
    }

    /**
     * 将 Float32Array 转换为 16-bit PCM
     * @param {Float32Array} floatArray 
     * @returns {Uint8Array}
     */
    floatTo16BitPCM(floatArray) {
        const pcmData = new Uint8Array(floatArray.length * 2);
        for (let i = 0; i < floatArray.length; i++) {
            const s = Math.max(-1, Math.min(1, floatArray[i]));
            const int16 = s < 0 ? s * 0x8000 : s * 0x7FFF;
            pcmData[i * 2] = int16 & 0xFF;
            pcmData[i * 2 + 1] = (int16 >> 8) & 0xFF;
        }
        return pcmData;
    }
}

// 导出
window.AudioRecorder = AudioRecorder;
```

- [ ] **Step 2: 提交 AudioRecorder 模块**

```bash
git add web_voice_assistant/static/app.js
git commit -m "feat: add AudioRecorder module for web voice assistant"
```

---

## Task 5: 编写前端 JavaScript - AudioPlayer 模块

**Files:**
- Modify: `web_voice_assistant/static/app.js`

- [ ] **Step 1: 添加 AudioPlayer 类到 app.js**

```javascript
/**
 * AudioPlayer - Web Audio API 音频播放模块
 * 负责播放后端传来的 PCM 音频数据
 */
class AudioPlayer {
    constructor() {
        this.audioContext = null;
        this.sampleRate = 24000; // TTS 输出采样率
        this.isPlaying = false;
        this.audioQueue = [];
        this.isProcessing = false;
    }

    /**
     * 初始化 AudioContext
     */
    init() {
        if (!this.audioContext) {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: this.sampleRate
            });
        }
    }

    /**
     * 播放 PCM 音频数据
     * @param {Uint8Array} pcmData - 16-bit PCM 数据
     */
    play(pcmData) {
        this.init();
        
        // 添加到队列
        this.audioQueue.push(pcmData);
        
        // 开始处理队列
        if (!this.isProcessing) {
            this.processQueue();
        }
    }

    /**
     * 处理音频队列
     */
    async processQueue() {
        if (this.isProcessing) return;
        this.isProcessing = true;

        while (this.audioQueue.length > 0) {
            const pcmData = this.audioQueue.shift();
            await this.playBuffer(pcmData);
        }

        this.isProcessing = false;
    }

    /**
     * 播放单个音频缓冲区
     * @param {Uint8Array} pcmData 
     */
    async playBuffer(pcmData) {
        return new Promise((resolve) => {
            if (!this.audioContext) {
                resolve();
                return;
            }

            // 将 Uint8Array 转换为 Float32Array
            const floatData = this.pcm16ToFloat32(pcmData);

            // 创建音频缓冲区
            const buffer = this.audioContext.createBuffer(1, floatData.length, this.sampleRate);
            buffer.getChannelData(0).set(floatData);

            // 创建音频源
            const source = this.audioContext.createBufferSource();
            source.buffer = buffer;
            source.connect(this.audioContext.destination);

            // 播放完成回调
            source.onended = () => {
                resolve();
            };

            // 开始播放
            source.start();
            this.isPlaying = true;
        });
    }

    /**
     * 停止播放
     */
    stop() {
        this.audioQueue = [];
        this.isProcessing = false;
        this.isPlaying = false;
        
        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }
    }

    /**
     * 将 16-bit PCM 转换为 Float32Array
     * @param {Uint8Array} pcmData 
     * @returns {Float32Array}
     */
    pcm16ToFloat32(pcmData) {
        const floatData = new Float32Array(pcmData.length / 2);
        for (let i = 0; i < floatData.length; i++) {
            const int16 = pcmData[i * 2] | (pcmData[i * 2 + 1] << 8);
            floatData[i] = int16 < 0x8000 ? int16 / 0x8000 : (int16 - 0x10000) / 0x8000;
        }
        return floatData;
    }
}

// 更新导出
window.AudioPlayer = AudioPlayer;
```

- [ ] **Step 2: 提交 AudioPlayer 模块**

```bash
git add web_voice_assistant/static/app.js
git commit -m "feat: add AudioPlayer module for web voice assistant"
```

---

## Task 6: 编写前端 JavaScript - ChatUI 模块

**Files:**
- Modify: `web_voice_assistant/static/app.js`

- [ ] **Step 1: 添加 ChatUI 类到 app.js**

```javascript
/**
 * ChatUI - 对话界面管理模块
 * 负责渲染消息和管理界面状态
 */
class ChatUI {
    constructor() {
        this.messagesContainer = document.getElementById('messages');
        this.statusElement = document.getElementById('status');
        this.recordBtn = document.getElementById('recordBtn');
        this.currentAIMessageId = null;
    }

    /**
     * 添加用户消息
     * @param {string} text - 消息内容
     */
    addUserMessage(text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user';
        messageDiv.textContent = text;
        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
    }

    /**
     * 添加 AI 消息（或创建占位）
     * @param {string} text - 初始消息内容（可选）
     * @returns {string} - 消息 ID
     */
    addAIMessage(text = '') {
        const messageId = 'ai-' + Date.now();
        this.currentAIMessageId = messageId;

        const messageDiv = document.createElement('div');
        messageDiv.id = messageId;
        messageDiv.className = 'message ai loading';
        messageDiv.innerHTML = text || '<span class="loading-dots">...</span>';
        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();

        return messageId;
    }

    /**
     * 更新 AI 消息内容
     * @param {string} text - 新内容
     * @param {boolean} done - 是否完成
     */
    updateAIMessage(text, done = false) {
        if (!this.currentAIMessageId) return;

        const messageDiv = document.getElementById(this.currentAIMessageId);
        if (messageDiv) {
            messageDiv.textContent = text;
            messageDiv.classList.remove('loading');
            
            if (done) {
                this.currentAIMessageId = null;
            }
        }
        this.scrollToBottom();
    }

    /**
     * 更新状态显示
     * @param {string} state - 状态: idle, recording, thinking, speaking, error
     */
    updateStatus(state) {
        const stateMap = {
            'idle': { text: '等待中...', class: '' },
            'recording': { text: '正在听...', class: 'recording' },
            'thinking': { text: '思考中...', class: 'thinking' },
            'speaking': { text: '播放中...', class: 'speaking' },
            'error': { text: '出错了', class: '' }
        };

        const stateInfo = stateMap[state] || stateMap['idle'];
        this.statusElement.textContent = stateInfo.text;
        this.statusElement.className = 'status ' + stateInfo.class;
    }

    /**
     * 设置录音按钮状态
     * @param {boolean} isRecording 
     */
    setRecordingState(isRecording) {
        if (isRecording) {
            this.recordBtn.classList.add('recording');
            this.recordBtn.querySelector('.btn-text').textContent = '松开结束';
        } else {
            this.recordBtn.classList.remove('recording');
            this.recordBtn.querySelector('.btn-text').textContent = '按住说话';
        }
    }

    /**
     * 滚动到底部
     */
    scrollToBottom() {
        const container = document.querySelector('.chat-container');
        container.scrollTop = container.scrollHeight;
    }

    /**
     * 显示错误信息
     * @param {string} message 
     */
    showError(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'message ai';
        errorDiv.style.background = '#ff4757';
        errorDiv.style.color = 'white';
        errorDiv.textContent = '❌ ' + message;
        this.messagesContainer.appendChild(errorDiv);
        this.scrollToBottom();
    }
}

// 更新导出
window.ChatUI = ChatUI;
```

- [ ] **Step 2: 提交 ChatUI 模块**

```bash
git add web_voice_assistant/static/app.js
git commit -m "feat: add ChatUI module for web voice assistant"
```

---

## Task 7: 编写前端 JavaScript - WebSocketClient 模块

**Files:**
- Modify: `web_voice_assistant/static/app.js`

- [ ] **Step 1: 添加 WebSocketClient 类到 app.js**

```javascript
/**
 * WebSocketClient - WebSocket 连接管理模块
 * 负责与后端建立连接和消息通信
 */
class WebSocketClient {
    constructor(url) {
        this.url = url;
        this.ws = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 3;
        this.onMessageCallback = null;
        this.onConnectCallback = null;
        this.onDisconnectCallback = null;
    }

    /**
     * 连接 WebSocket
     */
    connect() {
        return new Promise((resolve, reject) => {
            try {
                this.ws = new WebSocket(this.url);

                this.ws.onopen = () => {
                    console.log('[WebSocket] 连接成功');
                    this.isConnected = true;
                    this.reconnectAttempts = 0;
                    if (this.onConnectCallback) {
                        this.onConnectCallback();
                    }
                    resolve();
                };

                this.ws.onmessage = (event) => {
                    try {
                        const message = JSON.parse(event.data);
                        if (this.onMessageCallback) {
                            this.onMessageCallback(message);
                        }
                    } catch (error) {
                        console.error('[WebSocket] 解析消息失败:', error);
                    }
                };

                this.ws.onerror = (error) => {
                    console.error('[WebSocket] 错误:', error);
                    reject(error);
                };

                this.ws.onclose = () => {
                    console.log('[WebSocket] 连接关闭');
                    this.isConnected = false;
                    if (this.onDisconnectCallback) {
                        this.onDisconnectCallback();
                    }
                    this.attemptReconnect();
                };

            } catch (error) {
                reject(error);
            }
        });
    }

    /**
     * 尝试重连
     */
    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`[WebSocket] 尝试重连 (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
            setTimeout(() => {
                this.connect().catch(() => {});
            }, 2000);
        } else {
            console.error('[WebSocket] 重连次数超过限制');
        }
    }

    /**
     * 发送音频数据
     * @param {Uint8Array} pcmData 
     */
    sendAudio(pcmData) {
        if (!this.isConnected) return;

        // 将 PCM 数据转换为 Base64
        const base64Data = btoa(String.fromCharCode.apply(null, pcmData));
        
        this.send({
            type: 'audio',
            data: base64Data
        });
    }

    /**
     * 发送控制命令
     * @param {string} action - 'start_recording' | 'stop_recording'
     */
    sendControl(action) {
        if (!this.isConnected) return;

        this.send({
            type: 'control',
            action: action
        });
    }

    /**
     * 发送消息
     * @param {object} message 
     */
    send(message) {
        if (this.ws && this.isConnected) {
            this.ws.send(JSON.stringify(message));
        }
    }

    /**
     * 设置消息接收回调
     * @param {Function} callback 
     */
    onMessage(callback) {
        this.onMessageCallback = callback;
    }

    /**
     * 设置连接成功回调
     * @param {Function} callback 
     */
    onConnect(callback) {
        this.onConnectCallback = callback;
    }

    /**
     * 设置断开连接回调
     * @param {Function} callback 
     */
    onDisconnect(callback) {
        this.onDisconnectCallback = callback;
    }

    /**
     * 断开连接
     */
    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        this.isConnected = false;
    }
}

// 更新导出
window.WebSocketClient = WebSocketClient;
```

- [ ] **Step 2: 提交 WebSocketClient 模块**

```bash
git add web_voice_assistant/static/app.js
git commit -m "feat: add WebSocketClient module for web voice assistant"
```

---

## Task 8: 编写前端 JavaScript - 主应用逻辑

**Files:**
- Modify: `web_voice_assistant/static/app.js`

- [ ] **Step 1: 添加主应用逻辑到 app.js**

```javascript
/**
 * VoiceChatApp - 主应用类
 * 整合所有模块，管理整体流程
 */
class VoiceChatApp {
    constructor() {
        this.recorder = new AudioRecorder();
        this.player = new AudioPlayer();
        this.ui = new ChatUI();
        this.ws = new WebSocketClient('ws://localhost:8000/ws');
        this.isRecording = false;
        
        this.setupEventListeners();
        this.setupWebSocketHandlers();
    }

    /**
     * 设置事件监听
     */
    setupEventListeners() {
        const recordBtn = document.getElementById('recordBtn');

        // 鼠标/触摸事件
        recordBtn.addEventListener('mousedown', () => this.startRecording());
        recordBtn.addEventListener('mouseup', () => this.stopRecording());
        recordBtn.addEventListener('mouseleave', () => {
            if (this.isRecording) this.stopRecording();
        });

        // 触摸事件（移动端）
        recordBtn.addEventListener('touchstart', (e) => {
            e.preventDefault();
            this.startRecording();
        });
        recordBtn.addEventListener('touchend', (e) => {
            e.preventDefault();
            this.stopRecording();
        });
    }

    /**
     * 设置 WebSocket 消息处理
     */
    setupWebSocketHandlers() {
        this.ws.onMessage((message) => {
            this.handleServerMessage(message);
        });

        this.ws.onConnect(() => {
            console.log('[App] 已连接到服务器');
        });

        this.ws.onDisconnect(() => {
            console.log('[App] 与服务器断开连接');
            this.ui.updateStatus('error');
        });
    }

    /**
     * 开始录音
     */
    async startRecording() {
        if (this.isRecording) return;

        try {
            await this.recorder.start();
            this.isRecording = true;
            this.ui.setRecordingState(true);
            this.ui.updateStatus('recording');

            // 发送开始录音信号
            this.ws.sendControl('start_recording');

            // 设置音频数据回调
            this.recorder.onData((pcmData) => {
                if (this.isRecording) {
                    this.ws.sendAudio(pcmData);
                }
            });

        } catch (error) {
            console.error('[App] 开始录音失败:', error);
            this.ui.showError('无法访问麦克风，请检查权限设置');
            this.isRecording = false;
            this.ui.setRecordingState(false);
            this.ui.updateStatus('idle');
        }
    }

    /**
     * 停止录音
     */
    stopRecording() {
        if (!this.isRecording) return;

        this.isRecording = false;
        this.recorder.stop();
        this.ui.setRecordingState(false);
        this.ui.updateStatus('thinking');

        // 发送停止录音信号
        this.ws.sendControl('stop_recording');
    }

    /**
     * 处理服务器消息
     * @param {object} message 
     */
    handleServerMessage(message) {
        switch (message.type) {
            case 'status':
                this.ui.updateStatus(message.state);
                break;

            case 'transcription':
                // ASR 识别结果
                if (message.is_final) {
                    this.ui.addUserMessage(message.text);
                }
                break;

            case 'ai_text':
                // LLM 流式输出
                if (this.ui.currentAIMessageId) {
                    this.ui.updateAIMessage(message.text, message.done);
                } else {
                    this.ui.addAIMessage(message.text);
                }
                break;

            case 'audio':
                // TTS 音频数据
                this.ui.updateStatus('speaking');
                const pcmData = new Uint8Array(
                    atob(message.data).split('').map(c => c.charCodeAt(0))
                );
                this.player.play(pcmData);
                break;

            case 'complete':
                // 本轮对话完成
                this.ui.updateStatus('idle');
                break;

            case 'error':
                // 错误信息
                this.ui.showError(message.message);
                this.ui.updateStatus('idle');
                break;
        }
    }

    /**
     * 启动应用
     */
    async start() {
        try {
            await this.ws.connect();
            console.log('[App] 应用已启动');
        } catch (error) {
            console.error('[App] 连接服务器失败:', error);
            this.ui.showError('无法连接到服务器');
        }
    }
}

// 启动应用
document.addEventListener('DOMContentLoaded', () => {
    const app = new VoiceChatApp();
    app.start();
});
```

- [ ] **Step 2: 提交主应用逻辑**

```bash
git add web_voice_assistant/static/app.js
git commit -m "feat: add main app logic for web voice assistant"
```

---

## Task 9: 编写后端依赖文件

**Files:**
- Create: `web_voice_assistant/requirements-web.txt`

- [ ] **Step 1: 编写 requirements-web.txt**

```txt
fastapi>=0.100.0
uvicorn>=0.23.0
websockets>=11.0
python-multipart>=0.0.6

# 复用现有依赖
dashscope>=1.26.0
openai>=2.44.0
numpy>=1.24.0
pyyaml>=6.0.3
```

- [ ] **Step 2: 提交依赖文件**

```bash
git add web_voice_assistant/requirements-web.txt
git commit -m "chore: add requirements for web voice assistant"
```

---

## Task 10: 编写后端 chat_manager.py

**Files:**
- Create: `web_voice_assistant/chat_manager.py`

- [ ] **Step 1: 编写 chat_manager.py**

```python
"""
chat_manager.py
对话管理模块，处理 LLM 流式调用
"""
import os
from typing import AsyncGenerator
import openai


class ChatManager:
    """对话管理器"""
    
    def __init__(self):
        self.api_key = os.environ.get("LLM_API_KEY", "99161F95-3F04-45AA-831B-B976C8C23293")
        self.base_url = os.environ.get("LLM_BASE_URL", "http://192.168.16.10:8080/sourcing/v1")
        self.model = os.environ.get("LLM_MODEL", "qwen-turbo")
        
        self.client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
    
    async def stream_chat(self, user_message: str) -> AsyncGenerator[str, None]:
        """
        流式对话生成
        
        Args:
            user_message: 用户输入
            
        Yields:
            生成的文本片段
        """
        system_prompt = """你是一名招聘领域专属AI助手。

必须遵守以下规则：
- 仅回答招聘、人力资源、岗位、简历、面试、薪酬福利、招聘流程、人才管理等相关问题。
- 对任何非招聘领域的问题，一律回复："抱歉，我只能回答招聘相关的问题。"
- 回答保持专业、准确、简洁。
- 回复尽量控制在1~3句话，不超过50字。
- 不进行闲聊，不讲故事，不发表与招聘无关的观点。
"""
        
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                stream=True
            )
            
            for chunk in completion:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            print(f"[ChatManager] LLM 调用出错: {e}")
            yield "抱歉，服务暂时不可用，请稍后重试。"
```

- [ ] **Step 2: 提交 chat_manager.py**

```bash
git add web_voice_assistant/chat_manager.py
git commit -m "feat: add chat manager for web voice assistant"
```

---

## Task 11: 编写后端 audio_pipeline.py

**Files:**
- Create: `web_voice_assistant/audio_pipeline.py`

- [ ] **Step 1: 编写 audio_pipeline.py**

```python
"""
audio_pipeline.py
音频流处理模块，管理 ASR 和 TTS 的音频流
"""
import os
import queue
import threading
import time
from typing import Optional, Callable
import dashscope
from dashscope.audio.asr import Recognition, RecognitionCallback, RecognitionResult
from dashscope.audio.qwen_tts_realtime import QwenTtsRealtime, QwenTtsRealtimeCallback, AudioFormat


class ASRCallback(RecognitionCallback):
    """ASR 回调处理"""
    
    def __init__(self, on_text: Callable[[str, bool], None]):
        self.on_text = on_text
        self.mic = None
        self.stream = None
    
    def on_open(self) -> None:
        print('[ASR] 连接已建立')
    
    def on_close(self) -> None:
        print('[ASR] 连接已关闭')
    
    def on_complete(self) -> None:
        print('[ASR] 任务完成')
    
    def on_error(self, message) -> None:
        print(f'[ASR] 错误: {message.message}')
    
    def on_event(self, result: RecognitionResult) -> None:
        sentence = result.get_sentence()
        if 'text' in sentence:
            is_final = RecognitionResult.is_sentence_end(sentence)
            text = sentence['text']
            if text.strip():
                self.on_text(text, is_final)


class TTSCallback(QwenTtsRealtimeCallback):
    """TTS 回调处理"""
    
    def __init__(self, on_audio: Callable[[bytes], None]):
        self.on_audio = on_audio
        self.buffer = bytearray()
    
    def on_open(self):
        print('[TTS] 连接已建立')
    
    def on_close(self, code, msg):
        print(f'[TTS] 连接关闭: {code} {msg}')
    
    def on_event(self, response):
        event_type = response.get("type")
        if event_type == "response.audio.delta":
            import base64
            pcm = base64.b64decode(response["delta"])
            self.buffer.extend(pcm)
            # 积累一定量后发送
            if len(self.buffer) >= 4096:
                self.on_audio(bytes(self.buffer))
                self.buffer = bytearray()
        elif event_type == "response.done":
            # 发送剩余数据
            if self.buffer:
                self.on_audio(bytes(self.buffer))
                self.buffer = bytearray()


class AudioPipeline:
    """音频流处理管道"""
    
    def __init__(self, 
                 on_asr_text: Callable[[str, bool], None],
                 on_tts_audio: Callable[[bytes], None]):
        """
        初始化音频管道
        
        Args:
            on_asr_text: ASR 识别回调，参数为 (text, is_final)
            on_tts_audio: TTS 音频回调，参数为 pcm_bytes
        """
        self.on_asr_text = on_asr_text
        self.on_tts_audio = on_tts_audio
        
        # 配置
        self.api_key = os.environ.get("DASHSCOPE_API_KEY", "sk-5161496c3b6a4690b7a6c4a075a74181")
        dashscope.api_key = self.api_key
        
        # ASR
        self.asr_recognition: Optional[Recognition] = None
        self.asr_callback: Optional[ASRCallback] = None
        
        # TTS
        self.tts_client: Optional[QwenTtsRealtime] = None
        self.tts_callback: Optional[TTSCallback] = None
        self.tts_buffer = ""
        self.tts_lock = threading.Lock()
        
        # 音频队列
        self.audio_queue = queue.Queue()
        self.is_recording = False
    
    def start_asr(self):
        """启动 ASR"""
        self.asr_callback = ASRCallback(self.on_asr_text)
        self.asr_recognition = Recognition(
            model='fun-asr-realtime',
            format='pcm',
            sample_rate=16000,
            semantic_punctuation_enabled=False,
            callback=self.asr_callback
        )
        self.asr_recognition.start()
        self.is_recording = True
        print('[AudioPipeline] ASR 已启动')
    
    def stop_asr(self):
        """停止 ASR"""
        self.is_recording = False
        if self.asr_recognition:
            self.asr_recognition.stop()
            self.asr_recognition = None
        print('[AudioPipeline] ASR 已停止')
    
    def send_audio(self, pcm_data: bytes):
        """发送音频数据到 ASR"""
        if self.asr_recognition and self.is_recording:
            self.asr_recognition.send_audio_frame(pcm_data)
    
    def start_tts(self):
        """启动 TTS"""
        self.tts_callback = TTSCallback(self.on_tts_audio)
        self.tts_client = QwenTtsRealtime(
            model="qwen3-tts-flash-realtime",
            callback=self.tts_callback,
            url="wss://ws-pfc9xcvzdopof45u.cn-beijing.maas.aliyuncs.com/api-ws/v1/realtime"
        )
        self.tts_client.connect()
        self.tts_client.update_session(
            voice="Cherry",
            response_format=AudioFormat.PCM_24000HZ_MONO_16BIT,
            mode="server_commit"
        )
        print('[AudioPipeline] TTS 已启动')
    
    def stop_tts(self):
        """停止 TTS"""
        if self.tts_client:
            self.tts_client.finish()
            self.tts_client = None
        print('[AudioPipeline] TTS 已停止')
    
    def send_text_for_tts(self, text: str):
        """发送文本到 TTS"""
        if self.tts_client:
            with self.tts_lock:
                self.tts_buffer += text
                # 检查是否需要触发 flush
                if self._need_flush(self.tts_buffer):
                    self.tts_client.append_text(self.tts_buffer)
                    self.tts_buffer = ""
    
    def flush_tts(self):
        """刷新 TTS 缓冲区"""
        if self.tts_client:
            with self.tts_lock:
                if self.tts_buffer:
                    self.tts_client.append_text(self.tts_buffer)
                    self.tts_buffer = ""
            self.tts_client.finish()
    
    def _need_flush(self, text: str) -> bool:
        """检查是否需要触发 TTS flush"""
        if len(text) >= 20:  # 字符数达到 20
            return True
        if any(c in text for c in "，。！？；,.!?;"):  # 遇到标点
            return True
        return False
```

- [ ] **Step 2: 提交 audio_pipeline.py**

```bash
git add web_voice_assistant/audio_pipeline.py
git commit -m "feat: add audio pipeline for web voice assistant"
```

---

## Task 12: 编写后端 websocket_handler.py

**Files:**
- Create: `web_voice_assistant/websocket_handler.py`

- [ ] **Step 1: 编写 websocket_handler.py**

```python
"""
websocket_handler.py
WebSocket 连接处理模块
"""
import json
import asyncio
from typing import Dict, Set
from fastapi import WebSocket

from chat_manager import ChatManager
from audio_pipeline import AudioPipeline


class WebSocketManager:
    """WebSocket 连接管理器"""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.chat_manager = ChatManager()
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        print(f'[WebSocket] 新连接，当前连接数: {len(self.active_connections)}')
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        print(f'[WebSocket] 断开连接，当前连接数: {len(self.active_connections)}')
    
    async def send_message(self, websocket: WebSocket, message: Dict):
        """发送消息到客户端"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            print(f'[WebSocket] 发送消息失败: {e}')


class ConnectionHandler:
    """单个连接处理器"""
    
    def __init__(self, websocket: WebSocket, manager: WebSocketManager):
        self.websocket = websocket
        self.manager = manager
        self.audio_pipeline: AudioPipeline = None
        self.is_recording = False
        self.current_user_text = ""
        self.is_processing = False
    
    async def handle(self):
        """处理 WebSocket 连接"""
        try:
            while True:
                # 接收消息
                data = await self.websocket.receive_text()
                message = json.loads(data)
                await self.process_message(message)
                
        except Exception as e:
            print(f'[ConnectionHandler] 连接异常: {e}')
        finally:
            self.cleanup()
    
    async def process_message(self, message: Dict):
        """处理收到的消息"""
        msg_type = message.get('type')
        
        if msg_type == 'control':
            await self.handle_control(message)
        elif msg_type == 'audio':
            await self.handle_audio(message)
    
    async def handle_control(self, message: Dict):
        """处理控制消息"""
        action = message.get('action')
        
        if action == 'start_recording':
            await self.start_recording()
        elif action == 'stop_recording':
            await self.stop_recording()
    
    async def handle_audio(self, message: Dict):
        """处理音频数据"""
        if not self.is_recording:
            return
        
        # 解码 Base64 音频数据
        import base64
        audio_data = base64.b64decode(message.get('data', ''))
        
        # 发送到 ASR
        if self.audio_pipeline:
            self.audio_pipeline.send_audio(audio_data)
    
    async def start_recording(self):
        """开始录音"""
        if self.is_recording:
            return
        
        self.is_recording = True
        self.current_user_text = ""
        
        # 创建音频管道
        self.audio_pipeline = AudioPipeline(
            on_asr_text=self.on_asr_result,
            on_tts_audio=self.on_tts_audio
        )
        self.audio_pipeline.start_asr()
        
        # 发送状态更新
        await self.manager.send_message(self.websocket, {
            'type': 'status',
            'state': 'recording'
        })
        
        print('[ConnectionHandler] 开始录音')
    
    async def stop_recording(self):
        """停止录音"""
        if not self.is_recording:
            return
        
        self.is_recording = False
        
        # 停止 ASR
        if self.audio_pipeline:
            self.audio_pipeline.stop_asr()
        
        # 发送状态更新
        await self.manager.send_message(self.websocket, {
            'type': 'status',
            'state': 'thinking'
        })
        
        # 如果有识别文本，开始对话
        if self.current_user_text.strip() and not self.is_processing:
            asyncio.create_task(self.process_conversation())
        
        print('[ConnectionHandler] 停止录音')
    
    def on_asr_result(self, text: str, is_final: bool):
        """ASR 识别结果回调"""
        if is_final:
            self.current_user_text = text
            # 发送识别结果到前端
            asyncio.create_task(self.manager.send_message(self.websocket, {
                'type': 'transcription',
                'text': text,
                'is_final': True
            }))
    
    async def process_conversation(self):
        """处理对话流程"""
        self.is_processing = True
        
        try:
            # 启动 TTS
            self.audio_pipeline.start_tts()
            
            # 创建 AI 消息占位
            await self.manager.send_message(self.websocket, {
                'type': 'ai_text',
                'text': '',
                'done': False
            })
            
            # 流式调用 LLM
            full_response = ""
            async for text_chunk in self.chat_manager.stream_chat(self.current_user_text):
                full_response += text_chunk
                
                # 发送文本到前端
                await self.manager.send_message(self.websocket, {
                    'type': 'ai_text',
                    'text': full_response,
                    'done': False
                })
                
                # 发送文本到 TTS
                self.audio_pipeline.send_text_for_tts(text_chunk)
            
            # 刷新 TTS
            self.audio_pipeline.flush_tts()
            
            # 发送完成消息
            await self.manager.send_message(self.websocket, {
                'type': 'ai_text',
                'text': full_response,
                'done': True
            })
            
            await self.manager.send_message(self.websocket, {
                'type': 'complete'
            })
            
            await self.manager.send_message(self.websocket, {
                'type': 'status',
                'state': 'idle'
            })
            
        except Exception as e:
            print(f'[ConnectionHandler] 对话处理失败: {e}')
            await self.manager.send_message(self.websocket, {
                'type': 'error',
                'message': '对话处理失败，请重试'
            })
            await self.manager.send_message(self.websocket, {
                'type': 'status',
                'state': 'idle'
            })
        
        finally:
            self.is_processing = False
            self.current_user_text = ""
    
    def on_tts_audio(self, pcm_data: bytes):
        """TTS 音频数据回调"""
        import base64
        asyncio.create_task(self.manager.send_message(self.websocket, {
            'type': 'audio',
            'data': base64.b64encode(pcm_data).decode('utf-8')
        }))
    
    def cleanup(self):
        """清理资源"""
        if self.audio_pipeline:
            self.audio_pipeline.stop_asr()
            self.audio_pipeline.stop_tts()
            self.audio_pipeline = None


# WebSocket 管理器实例
ws_manager = WebSocketManager()


async def handle_websocket(websocket: WebSocket):
    """处理 WebSocket 连接"""
    await ws_manager.connect(websocket)
    
    try:
        handler = ConnectionHandler(websocket, ws_manager)
        await handler.handle()
    finally:
        ws_manager.disconnect(websocket)
```

- [ ] **Step 2: 提交 websocket_handler.py**

```bash
git add web_voice_assistant/websocket_handler.py
git commit -m "feat: add websocket handler for web voice assistant"
```

---

## Task 13: 编写后端 main.py

**Files:**
- Create: `web_voice_assistant/main.py`

- [ ] **Step 1: 编写 main.py**

```python
"""
main.py
FastAPI 入口，启动 WebSocket 服务
"""
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn

from websocket_handler import handle_websocket

# 创建 FastAPI 应用
app = FastAPI(title="语音对话助手", version="1.0.0")

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    """根路由，返回主页面"""
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 端点"""
    await handle_websocket(websocket)


if __name__ == "__main__":
    print("=" * 60)
    print("语音对话助手服务")
    print("=" * 60)
    print("服务地址: http://localhost:8000")
    print("WebSocket: ws://localhost:8000/ws")
    print("=" * 60)
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
```

- [ ] **Step 2: 提交 main.py**

```bash
git add web_voice_assistant/main.py
git commit -m "feat: add main entry for web voice assistant"
```

---

## Task 14: 测试和运行

**Files:**
- All files

- [ ] **Step 1: 安装依赖**

```bash
cd web_voice_assistant
pip install -r requirements-web.txt
```

- [ ] **Step 2: 启动服务**

```bash
cd web_voice_assistant
python main.py
```

- [ ] **Step 3: 测试功能**

在浏览器中访问 `http://localhost:8000`，测试以下功能：

1. 页面加载成功，显示"等待中..."
2. 按住"按住说话"按钮，状态变为"正在听..."
3. 对着麦克风说话，松开按钮
4. 状态变为"思考中..."
5. AI 回复文字逐字显示
6. AI 语音自动播放
7. 状态恢复"等待中..."
8. 可以进行下一轮对话

- [ ] **Step 4: 提交完成**

```bash
git add .
git commit -m "feat: complete web voice assistant implementation"
```

---

## 自检清单

**1. Spec coverage:**
- ✅ WebSocket 实时音频流传输 - Task 7, 12, 13
- ✅ DashScope ASR 集成 - Task 11
- ✅ LLM 流式对话 - Task 10
- ✅ DashScope TTS 实时播放 - Task 11
- ✅ 状态机和错误处理 - Task 8, 12
- ✅ 响应式 UI 设计 - Task 2, 3
- ✅ 麦克风权限处理 - Task 8

**2. Placeholder scan:**
- ✅ 无 TBD/TODO
- ✅ 无未完成的占位符
- ✅ 所有代码都有具体实现

**3. Type consistency:**
- ✅ AudioRecorder 类名一致
- ✅ WebSocketClient 类名一致
- ✅ ChatManager 类名一致
- ✅ 消息格式一致 (type/data 结构)

---

## 后续扩展建议

1. **多用户支持**: 使用 session_id 区分不同用户
2. **对话历史**: 添加数据库保存对话记录
3. **用户认证**: 添加 JWT 认证机制
4. **音频可视化**: 添加录音波形动画
5. **移动端优化**: 添加 PWA 支持
6. **多语言支持**: 支持英文 ASR/TTS

---

*计划版本: 1.0*  
*基于设计文档: docs/superpowers/specs/2026-07-10-web-voice-assistant-design.md*
