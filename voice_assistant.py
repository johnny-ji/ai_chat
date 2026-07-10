"""
voice_assistant.py
整合 FunASR 实时语音识别 + 大模型流式对话 + Qwen3-TTS 实时语音合成
完整流程：麦克风录音 -> 实时ASR -> LLM流式回复 -> TTS实时播放

相比原三个独立文件的改动：
1. TTSPlayer 只在程序启动时创建一次并常驻，避免每轮对话都重连 websocket（原来延迟很高）。
2. OpenAI client 只创建一次并复用。
3. 增加"播放期间暂停发送麦克风音频"的互斥逻辑，避免外放声音被识别回去造成自问自答。
4. 统一 Ctrl+C 退出时的资源清理（ASR + TTS + 麦克风）。
"""

import os
import signal
import sys
import threading
import time

import numpy as np
import dashscope
import pyaudio
from dashscope.audio.asr import *
from openai import OpenAI

from tts_player import TTSPlayer

# ============ 配置 ============
DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "sk-5161496c3b6a4690b7a6c4a075a74181")
ASR_WS_URL = 'wss://ws-pfc9xcvzdopof45u.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference'

LLM_API_KEY = os.environ.get("LLM_API_KEY", "99161F95-3F04-45AA-831B-B976C8C23293")
LLM_BASE_URL = "http://192.168.16.10:8080/sourcing/v1"
LLM_MODEL = "qwen-turbo"

# 录音参数
SAMPLE_RATE = 16000
FORMAT_PCM = 'pcm'
BLOCK_SIZE = 3200  # 约100ms

# 客户端静音过滤参数
ENERGY_THRESHOLD = 300       # 低于此能量视为环境噪音
SPEECH_HANG_FRAMES = 30      # 语音结束后继续发送的帧数，避免截断词尾
KEEPALIVE_INTERVAL_FRAMES = 100  # 静音时每隔多少帧发一次保活帧

# ============ 全局状态 ============
mic = None
stream = None
recognition = None
tts_player = None
llm_client = None

# 播放期间暂停发送音频，避免外放声音被再次识别（自问自答）
is_speaking = threading.Event()


class Callback(RecognitionCallback):
    def on_open(self) -> None:
        global mic, stream
        print('[ASR] 连接已建立，开始监听麦克风...')
        mic = pyaudio.PyAudio()
        stream = mic.open(format=pyaudio.paInt16,
                           channels=1,
                           rate=SAMPLE_RATE,
                           input=True)

    def on_close(self) -> None:
        global mic, stream
        print('[ASR] 连接已关闭')
        if stream is not None:
            stream.stop_stream()
            stream.close()
        if mic is not None:
            mic.terminate()
        stream = None
        mic = None

    def on_complete(self) -> None:
        print('[ASR] 任务完成')

    def on_error(self, message) -> None:
        print('[ASR] 错误, request_id:', message.request_id)
        print('[ASR] 错误信息:', message.message)
        if stream is not None and stream.is_active():
            stream.stop_stream()
            stream.close()
        sys.exit(1)

    def on_event(self, result: RecognitionResult) -> None:
        sentence = result.get_sentence()
        if 'text' in sentence:
            if RecognitionResult.is_sentence_end(sentence):
                text = sentence['text']
                print(f"[ASR] 识别到完整句子: {text}")
                if not text.strip():
                    return
                # 开一个线程处理LLM+TTS，避免阻塞ASR的音频接收
                threading.Thread(target=handle_turn, args=(text,), daemon=True).start()


def handle_turn(user_message: str):
    """处理一轮对话：调用LLM流式生成，边生成边送入TTS播放"""
    global llm_client, tts_player

    is_speaking.set()  # 暂停发送麦克风音频，防止回声被识别
    try:
        print(f"[LLM] 用户: {user_message}")
        print("[LLM] 助手: ", end="", flush=True)

        completion = llm_client.chat.completions.create(
            model=LLM_MODEL,
            messages = [
                {"role": "system",
                 "content": """
                        你是一名招聘领域专属AI助手。

                        必须遵守以下规则：
                        - 仅回答招聘、人力资源、岗位、简历、面试、薪酬福利、招聘流程、人才管理等相关问题。
                        - 对任何非招聘领域的问题，一律回复：
                        "抱歉，我只能回答招聘相关的问题。"
                        - 回答保持专业、准确、简洁。
                        - 回复尽量控制在1~3句话，不超过50字。
                        - 不进行闲聊，不讲故事，不发表与招聘无关的观点。
                        """
                },
                {"role": "user","content": user_message,},
                ],
            stream=True,
        )

        for chunk in completion:
            if chunk.choices and chunk.choices[0].delta.content:
                text = chunk.choices[0].delta.content
                print(text, end="", flush=True)
                tts_player.speak(text)

        print()
        tts_player.flush()  # 把剩余buffer发出去，并告知本轮结束
    except Exception as e:
        print(f"\n[LLM] 调用出错: {e}")
    finally:
        # 简单起见，flush完立即恢复录音；如需更精确可以在TTS播放完成回调里再恢复
        is_speaking.clear()


def signal_handler(sig, frame):
    print('\n收到 Ctrl+C，正在停止...')
    try:
        if recognition is not None:
            recognition.stop()
            print('[ASR] 已停止')
            print('[Metric] requestId: {}, first package delay ms: {}, last package delay ms: {}'.format(
                recognition.get_last_request_id(),
                recognition.get_first_package_delay(),
                recognition.get_last_package_delay(),
            ))
    except Exception as e:
        print(f"停止ASR时出错: {e}")

    try:
        if tts_player is not None:
            tts_player.stop()
            print('[TTS] 已停止')
    except Exception as e:
        print(f"停止TTS时出错: {e}")

    sys.exit(0)


def main():
    global recognition, tts_player, llm_client

    dashscope.api_key = DASHSCOPE_API_KEY
    dashscope.base_websocket_api_url = ASR_WS_URL

    # 初始化 LLM client（只创建一次，复用连接）
    llm_client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

    # 初始化 TTS player（只创建一次，常驻连接，避免每轮对话都重连）
    tts_player = TTSPlayer(api_key=DASHSCOPE_API_KEY)
    tts_player.start()

    # 初始化 ASR
    callback = Callback()
    recognition = Recognition(
        model='fun-asr-realtime',
        format=FORMAT_PCM,
        sample_rate=SAMPLE_RATE,
        semantic_punctuation_enabled=False,
        callback=callback,
    )
    recognition.start()

    signal.signal(signal.SIGINT, signal_handler)
    print("语音助手已启动，请对着麦克风说话。按 'Ctrl+C' 退出...")

    speech_hang_counter = 0
    silence_frame_counter = 0

    while True:
        if stream is None:
            break

        data = stream.read(BLOCK_SIZE, exception_on_overflow=False)

        # TTS播放期间不发送音频，避免外放声音被识别形成自问自答
        if is_speaking.is_set():
            continue

        audio_array = np.frombuffer(data, dtype=np.int16)
        rms = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))

        if rms >= ENERGY_THRESHOLD:
            recognition.send_audio_frame(data)
            speech_hang_counter = SPEECH_HANG_FRAMES
            silence_frame_counter = 0
        elif speech_hang_counter > 0:
            recognition.send_audio_frame(data)
            speech_hang_counter -= 1
            silence_frame_counter = 0
        else:
            silence_frame_counter += 1
            if silence_frame_counter >= KEEPALIVE_INTERVAL_FRAMES:
                recognition.send_audio_frame(data)
                silence_frame_counter = 0

    recognition.stop()


if __name__ == '__main__':
    # 运行主程序
    main()