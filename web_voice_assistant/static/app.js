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

    async start() {
        if (this.isRecording) return;

        try {
            this.stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: 16000,
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true
                }
            });

            this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: 16000
            });

            this.source = this.audioContext.createMediaStreamSource(this.stream);
            const bufferSize = 2048;
            this.processor = this.audioContext.createScriptProcessor(bufferSize, 1, 1);

            this.processor.onaudioprocess = (event) => {
                if (!this.isRecording) return;
                const inputData = event.inputBuffer.getChannelData(0);
                const pcmData = this.floatTo16BitPCM(inputData);
                if (this.onDataCallback) {
                    this.onDataCallback(pcmData);
                }
            };

            this.source.connect(this.processor);
            this.processor.connect(this.audioContext.destination);
            this.isRecording = true;
            console.log('[AudioRecorder] 开始录音');
        } catch (error) {
            console.error('[AudioRecorder] 录音失败:', error);
            throw error;
        }
    }

    stop() {
        if (!this.isRecording) return;
        this.isRecording = false;
        if (this.processor) { this.processor.disconnect(); this.processor = null; }
        if (this.source) { this.source.disconnect(); this.source = null; }
        if (this.audioContext) { this.audioContext.close(); this.audioContext = null; }
        if (this.stream) { this.stream.getTracks().forEach(track => track.stop()); this.stream = null; }
        console.log('[AudioRecorder] 停止录音');
    }

    onData(callback) { this.onDataCallback = callback; }

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

/**
 * AudioPlayer - Web Audio API 音频播放模块
 * 负责播放后端传来的 PCM 音频数据
 */
class AudioPlayer {
    constructor() {
        this.audioContext = null;
        this.sampleRate = 24000;
        this.isPlaying = false;
        this.audioQueue = [];
        this.isProcessing = false;
    }

    init() {
        if (!this.audioContext) {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: this.sampleRate
            });
        }
    }

    play(pcmData) {
        this.init();
        this.audioQueue.push(pcmData);
        if (!this.isProcessing) { this.processQueue(); }
    }

    async processQueue() {
        if (this.isProcessing) return;
        this.isProcessing = true;
        while (this.audioQueue.length > 0) {
            const pcmData = this.audioQueue.shift();
            await this.playBuffer(pcmData);
        }
        this.isProcessing = false;
    }

    async playBuffer(pcmData) {
        return new Promise((resolve) => {
            if (!this.audioContext) { resolve(); return; }
            const floatData = this.pcm16ToFloat32(pcmData);
            const buffer = this.audioContext.createBuffer(1, floatData.length, this.sampleRate);
            buffer.getChannelData(0).set(floatData);
            const source = this.audioContext.createBufferSource();
            source.buffer = buffer;
            source.connect(this.audioContext.destination);
            source.onended = () => { resolve(); };
            source.start();
            this.isPlaying = true;
        });
    }

    stop() {
        this.audioQueue = [];
        this.isProcessing = false;
        this.isPlaying = false;
        if (this.audioContext) { this.audioContext.close(); this.audioContext = null; }
    }

    pcm16ToFloat32(pcmData) {
        const floatData = new Float32Array(pcmData.length / 2);
        for (let i = 0; i < floatData.length; i++) {
            const int16 = pcmData[i * 2] | (pcmData[i * 2 + 1] << 8);
            floatData[i] = int16 < 0x8000 ? int16 / 0x8000 : (int16 - 0x10000) / 0x8000;
        }
        return floatData;
    }
}

/**
 * ChatUI - 对话界面管理模块
 */
class ChatUI {
    constructor() {
        this.messagesContainer = document.getElementById('messages');
        this.statusElement = document.getElementById('status');
        this.recordBtn = document.getElementById('recordBtn');
        this.currentAIMessageId = null;
    }

    addUserMessage(text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user';
        messageDiv.textContent = text;
        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
    }

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

    updateAIMessage(text, done = false) {
        if (!this.currentAIMessageId) return;
        const messageDiv = document.getElementById(this.currentAIMessageId);
        if (messageDiv) {
            messageDiv.textContent = text;
            messageDiv.classList.remove('loading');
            if (done) { this.currentAIMessageId = null; }
        }
        this.scrollToBottom();
    }

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

    setRecordingState(isRecording) {
        if (isRecording) {
            this.recordBtn.classList.add('recording');
            this.recordBtn.querySelector('.btn-text').textContent = '松开结束';
        } else {
            this.recordBtn.classList.remove('recording');
            this.recordBtn.querySelector('.btn-text').textContent = '按住说话';
        }
    }

    scrollToBottom() {
        const container = document.querySelector('.chat-container');
        container.scrollTop = container.scrollHeight;
    }

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

/**
 * WebSocketClient - WebSocket 连接管理模块
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

    connect() {
        return new Promise((resolve, reject) => {
            try {
                this.ws = new WebSocket(this.url);
                this.ws.onopen = () => {
                    console.log('[WebSocket] 连接成功');
                    this.isConnected = true;
                    this.reconnectAttempts = 0;
                    if (this.onConnectCallback) { this.onConnectCallback(); }
                    resolve();
                };
                this.ws.onmessage = (event) => {
                    try {
                        const message = JSON.parse(event.data);
                        if (this.onMessageCallback) { this.onMessageCallback(message); }
                    } catch (error) { console.error('[WebSocket] 解析消息失败:', error); }
                };
                this.ws.onerror = (error) => { console.error('[WebSocket] 错误:', error); reject(error); };
                this.ws.onclose = () => {
                    console.log('[WebSocket] 连接关闭');
                    this.isConnected = false;
                    if (this.onDisconnectCallback) { this.onDisconnectCallback(); }
                    this.attemptReconnect();
                };
            } catch (error) { reject(error); }
        });
    }

    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`[WebSocket] 尝试重连 (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
            setTimeout(() => { this.connect().catch(() => {}); }, 2000);
        } else { console.error('[WebSocket] 重连次数超过限制'); }
    }

    sendAudio(pcmData) {
        if (!this.isConnected) return;
        const base64Data = btoa(String.fromCharCode.apply(null, pcmData));
        this.send({ type: 'audio', data: base64Data });
    }

    sendControl(action) {
        if (!this.isConnected) return;
        this.send({ type: 'control', action: action });
    }

    send(message) {
        if (this.ws && this.isConnected) { this.ws.send(JSON.stringify(message)); }
    }

    onMessage(callback) { this.onMessageCallback = callback; }
    onConnect(callback) { this.onConnectCallback = callback; }
    onDisconnect(callback) { this.onDisconnectCallback = callback; }

    disconnect() {
        if (this.ws) { this.ws.close(); this.ws = null; }
        this.isConnected = false;
    }
}

/**
 * VoiceChatApp - 主应用类
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

    setupEventListeners() {
        const recordBtn = document.getElementById('recordBtn');
        recordBtn.addEventListener('mousedown', () => this.startRecording());
        recordBtn.addEventListener('mouseup', () => this.stopRecording());
        recordBtn.addEventListener('mouseleave', () => { if (this.isRecording) this.stopRecording(); });
        recordBtn.addEventListener('touchstart', (e) => { e.preventDefault(); this.startRecording(); });
        recordBtn.addEventListener('touchend', (e) => { e.preventDefault(); this.stopRecording(); });
    }

    setupWebSocketHandlers() {
        this.ws.onMessage((message) => { this.handleServerMessage(message); });
        this.ws.onConnect(() => { console.log('[App] 已连接到服务器'); });
        this.ws.onDisconnect(() => { console.log('[App] 与服务器断开连接'); this.ui.updateStatus('error'); });
    }

    async startRecording() {
        if (this.isRecording) return;
        try {
            await this.recorder.start();
            this.isRecording = true;
            this.ui.setRecordingState(true);
            this.ui.updateStatus('recording');
            this.ws.sendControl('start_recording');
            this.recorder.onData((pcmData) => {
                if (this.isRecording) { this.ws.sendAudio(pcmData); }
            });
        } catch (error) {
            console.error('[App] 开始录音失败:', error);
            this.ui.showError('无法访问麦克风，请检查权限设置');
            this.isRecording = false;
            this.ui.setRecordingState(false);
            this.ui.updateStatus('idle');
        }
    }

    stopRecording() {
        if (!this.isRecording) return;
        this.isRecording = false;
        this.recorder.stop();
        this.ui.setRecordingState(false);
        this.ui.updateStatus('thinking');
        this.ws.sendControl('stop_recording');
    }

    handleServerMessage(message) {
        switch (message.type) {
            case 'status': this.ui.updateStatus(message.state); break;
            case 'transcription': if (message.is_final) { this.ui.addUserMessage(message.text); } break;
            case 'ai_text':
                if (this.ui.currentAIMessageId) { this.ui.updateAIMessage(message.text, message.done); }
                else { this.ui.addAIMessage(message.text); }
                break;
            case 'audio':
                this.ui.updateStatus('speaking');
                const pcmData = new Uint8Array(atob(message.data).split('').map(c => c.charCodeAt(0)));
                this.player.play(pcmData);
                break;
            case 'complete': this.ui.updateStatus('idle'); break;
            case 'error': this.ui.showError(message.message); this.ui.updateStatus('idle'); break;
        }
    }

    async start() {
        try { await this.ws.connect(); console.log('[App] 应用已启动'); }
        catch (error) { console.error('[App] 连接服务器失败:', error); this.ui.showError('无法连接到服务器'); }
    }
}

// 启动应用
document.addEventListener('DOMContentLoaded', () => {
    const app = new VoiceChatApp();
    app.start();
});
