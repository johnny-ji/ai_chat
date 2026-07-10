import os
import signal  # 用于处理键盘事件（按 "Ctrl+C" 终止录音）
import sys
import numpy as np

import dashscope
import pyaudio
from dashscope.audio.asr import *

from llm_util import chat_with_streaming_response

# 全局麦克风和音频流对象
mic = None
stream = None

# 录音参数配置
sample_rate = 16000  # 采样率（Hz）
channels = 1         # 单声道
dtype = 'int16'      # 数据类型（16位整型）
format_pcm = 'pcm'   # 音频数据格式
block_size = 3200    # 每次读取的帧数（约100ms的音频）

# 客户端静音过滤参数（降低误识别灵敏度）
# RMS 能量阈值：低于此值的帧被视为环境噪音/远处声音，不发送给识别服务
# 取值参考：安静环境可设 300~500，嘈杂环境可适当提高至 800~1500
ENERGY_THRESHOLD = 300
# 检测到语音后，能量降回阈值以下时仍继续发送的帧数（防止截断词尾和句尾停顿）
SPEECH_HANG_FRAMES = 30
# 静音保活间隔（帧数）：长时间静音时，每隔此帧数发送一帧静音，防止服务因无音频而报 EmptyAudio/超时
# 3200帧约100ms，故 100 帧约 10 秒发送一次保活帧
KEEPALIVE_INTERVAL_FRAMES = 100

# 实时语音识别回调类
class Callback(RecognitionCallback):
    def on_open(self) -> None:
        """识别连接建立时的回调：初始化麦克风和音频输入流"""
        global mic
        global stream
        print('语音识别回调连接已建立...')
        mic = pyaudio.PyAudio()
        stream = mic.open(format=pyaudio.paInt16,
                          channels=1,
                          rate=16000,
                          input=True)

    def on_close(self) -> None:
        """识别连接关闭时的回调：释放音频流和麦克风资源"""
        global mic
        global stream
        print('语音识别回调连接已关闭...')
        stream.stop_stream()
        stream.close()
        mic.terminate()
        stream = None
        mic = None

    def on_complete(self) -> None:
        """识别任务完成时的回调"""
        print('语音识别回调任务已完成...')

    def on_error(self, message) -> None:
        """识别出错时的回调：打印错误信息并强制退出程序"""
        print('语音识别回调任务ID: ', message.request_id)
        print('语音识别回调错误: ', message.message)
        # 若音频流仍在运行则停止并关闭
        if 'stream' in globals() and stream is not None and stream.is_active():
            stream.stop_stream()
            stream.close()
        # 强制退出程序
        sys.exit(1)

    def on_event(self, result: RecognitionResult) -> None:
        """收到识别结果时的回调：打印实时识别文本，句子结束时打印统计信息"""
        sentence = result.get_sentence()
        if 'text' in sentence:
            # print('语音识别回调文本: ', sentence['text'])
            if RecognitionResult.is_sentence_end(sentence):
                # 句子识别完成，打印请求ID和用量信息
                print(
                    '语音识别回调句子结束, 文本: %s, request_id: %s, usage: %s'
                    % (sentence['text'], result.get_request_id(), result.get_usage(sentence)))
                chat_with_streaming_response(sentence['text'])

def signal_handler(sig, frame):
    """Ctrl+C 信号处理函数：停止识别并打印性能指标后退出"""
    print('Ctrl+C pressed, stop recognition ...')
    # 停止语音识别
    recognition.stop()
    print('语音识别已停止')
    # 打印请求ID及首包/尾包延迟指标
    print(
        '[Metric] requestId: {}, first package delay ms: {}, last package delay ms: {}'
        .format(
            recognition.get_last_request_id(),
            recognition.get_first_package_delay(),
            recognition.get_last_package_delay(),
        ))
    # 正常退出程序
    sys.exit(0)

# 主程序入口
if __name__ == '__main__':
    # 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
    # 若没有配置环境变量，请用百炼API Key将下行替换为：dashscope.api_key = "sk-xxx"
    dashscope.api_key = "sk-5161496c3b6a4690b7a6c4a075a74181"

    # 以下为华北2（北京）地域的配置，调用时请将"{WorkspaceId}"替换为真实的业务空间ID，各地域的配置不同。
    dashscope.base_websocket_api_url='wss://ws-pfc9xcvzdopof45u.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference'

    # 创建识别回调实例
    callback = Callback()

    # 以异步模式调用语音识别服务，可自定义模型、格式、采样率等参数
    recognition = Recognition(
        model='fun-asr-realtime',
        format=format_pcm,
        # 支持格式：'pcm'、'wav'、'opus'、'speex'、'aac'、'amr'，详见文档
        sample_rate=sample_rate,
        # 支持采样率：8000、16000
        semantic_punctuation_enabled=False,
        callback=callback)

    # 启动语音识别
    recognition.start()

    # 注册 Ctrl+C 信号处理函数
    signal.signal(signal.SIGINT, signal_handler)
    print("按 'Ctrl+C' 停止录音和识别...")

    # 持续从麦克风读取音频数据并发送给识别服务，直到流关闭
    speech_hang_counter = 0    # 语音挂起计数器：在语音结束后延迟停止发送，避免截断词尾
    silence_frame_counter = 0  # 静音帧计数器：累计连续丢弃的静音帧，用于触发定期保活
    while True:
        if stream:
            data = stream.read(3200, exception_on_overflow=False)

            # 计算当前帧的 RMS 能量，用于判断是否为有效语音
            audio_array = np.frombuffer(data, dtype=np.int16)
            rms = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))

            if rms >= ENERGY_THRESHOLD:
                # 能量超过阈值：判定为有效语音，发送并重置计数器
                recognition.send_audio_frame(data)
                speech_hang_counter = SPEECH_HANG_FRAMES
                silence_frame_counter = 0
            elif speech_hang_counter > 0:
                # 能量低于阈值，但处于挂起保护期内：继续发送以保证句尾完整
                recognition.send_audio_frame(data)
                speech_hang_counter -= 1
                silence_frame_counter = 0
            else:
                # 静音/噪音帧：默认不发送，但定期发送一帧保活，避免 EmptyAudio/超时
                silence_frame_counter += 1
                if silence_frame_counter >= KEEPALIVE_INTERVAL_FRAMES:
                    recognition.send_audio_frame(data)
                    silence_frame_counter = 0

        else:
            break

    recognition.stop()