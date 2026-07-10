"""audio_pipeline.py - 音频流处理模块，管理 ASR 和 TTS 的音频流"""
import os
import threading
from typing import Optional, Callable
import dashscope
from dashscope.audio.asr import Recognition, RecognitionCallback, RecognitionResult
from dashscope.audio.qwen_tts_realtime import QwenTtsRealtime, QwenTtsRealtimeCallback, AudioFormat


class ASRCallback(RecognitionCallback):
    """ASR 回调处理"""

    def __init__(self, on_text: Callable[[str, bool], None]):
        self.on_text = on_text

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
        import base64
        event_type = response.get("type")
        if event_type == "response.audio.delta":
            pcm = base64.b64decode(response["delta"])
            self.buffer.extend(pcm)
            if len(self.buffer) >= 4096:
                self.on_audio(bytes(self.buffer))
                self.buffer = bytearray()
        elif event_type == "response.done":
            if self.buffer:
                self.on_audio(bytes(self.buffer))
                self.buffer = bytearray()


class AudioPipeline:
    """音频流处理管道"""

    def __init__(self,
                 on_asr_text: Callable[[str, bool], None],
                 on_tts_audio: Callable[[bytes], None]):
        self.on_asr_text = on_asr_text
        self.on_tts_audio = on_tts_audio

        self.api_key = os.environ.get("DASHSCOPE_API_KEY", "sk-5161496c3b6a4690b7a6c4a075a74181")
        dashscope.api_key = self.api_key

        self.asr_recognition: Optional[Recognition] = None
        self.asr_callback: Optional[ASRCallback] = None

        self.tts_client: Optional[QwenTtsRealtime] = None
        self.tts_callback: Optional[TTSCallback] = None
        self.tts_buffer = ""
        self.tts_lock = threading.Lock()
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
        if len(text) >= 20:
            return True
        if any(c in text for c in "，。！？；,.!?;"):
            return True
        return False
