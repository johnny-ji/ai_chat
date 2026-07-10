"""
tts_player.py
生产版 Qwen3-TTS 流式播放器
"""
import base64
import queue
import threading
import time
import dashscope
import sounddevice as sd
from dashscope.audio.qwen_tts_realtime import QwenTtsRealtime,QwenTtsRealtimeCallback,AudioFormat

class TTSCallback(QwenTtsRealtimeCallback):
    def __init__(self, save_pcm=False, pcm_file="result_24k.pcm"):
        self.stream = sd.RawOutputStream(samplerate=24000, channels=1, dtype="int16")
        self.stream.start()
        self.file = open(pcm_file,"wb") if save_pcm else None

    def on_open(self):
        print("[TTS] connected")

    def on_close(self, code, msg):
        print(f"[TTS] closed {code} {msg}")
        if self.file:
            self.file.close()
        self.stream.stop()
        self.stream.close()

    def on_event(self, response):
        t = response.get("type")
        if t == "response.audio.delta":
            pcm = base64.b64decode(response["delta"])
            if self.file:
                self.file.write(pcm)
            self.stream.write(pcm)
        elif t == "response.done":
            print("[TTS] sentence done")
        elif t == "session.created":
            print("[TTS] session", response["session"]["id"])

class TTSPlayer:
    def __init__(self, api_key, voice="Cherry",
                 url="wss://ws-pfc9xcvzdopof45u.cn-beijing.maas.aliyuncs.com/api-ws/v1/realtime",
                 save_pcm=False):
        dashscope.api_key = api_key
        self.voice=voice
        self.url=url
        self.callback=TTSCallback(save_pcm)
        self.client=None
        self.q=queue.Queue()
        self.running=False
        self.sender=None
        self.buf=""
        self.last=time.time()
        self.flush_chars=20
        self.flush_interval=0.15

    def start(self):
        self.client=QwenTtsRealtime(model="qwen3-tts-flash-realtime",
                                    callback=self.callback,url=self.url)
        self.client.connect()
        self.client.update_session(
            voice=self.voice,
            response_format=AudioFormat.PCM_24000HZ_MONO_16BIT,
            mode="server_commit")
        self.running=True
        self.sender=threading.Thread(target=self._loop,daemon=True)
        self.sender.start()

    def speak(self,text):
        if text:
            self.q.put(text)

    def _need_flush(self,s):
        return len(s)>=self.flush_chars or any(x in s for x in "，。！？；,.!?;")

    def _loop(self):
        while self.running:
            try:
                t=self.q.get(timeout=0.05)
                self.buf+=t
                self.last=time.time()
            except queue.Empty:
                pass
            if self.buf and (self._need_flush(self.buf) or time.time()-self.last>self.flush_interval):
                self.client.append_text(self.buf)
                self.buf=""

    def flush(self):
        while not self.q.empty():
            time.sleep(0.02)
        if self.buf:
            self.client.append_text(self.buf)
            self.buf=""
        self.client.finish()

    def stop(self):
        self.running=False
        if self.sender:
            self.sender.join(timeout=1)
        try:
            self.flush()
        except Exception:
            pass

if __name__=="__main__":
    tts=TTSPlayer(api_key="sk-5161496c3b6a4690b7a6c4a075a74181",save_pcm=True)
    tts.start()
    for s in ["你好，","我是朝朝。","很高兴为您服务！"]:
        tts.speak(s)
        time.sleep(0.05)
    tts.flush()
    input("Press Enter to exit...")
    tts.stop()