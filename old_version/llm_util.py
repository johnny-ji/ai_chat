import os
from openai import OpenAI
from tts_player import TTSPlayer
import time



def chat_with_streaming_response(user_message: str):
    """
    使用流式响应进行聊天。
    """
    tts = TTSPlayer(api_key="sk-5161496c3b6a4690b7a6c4a075a74181")
    tts.start()
    client = OpenAI(
        # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key="sk-xxx",
        api_key="99161F95-3F04-45AA-831B-B976C8C23293",
        base_url="http://192.168.16.10:8080/sourcing/v1",
    )
    completion = client.chat.completions.create(
        model="qwen-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": user_message},
        ],
        stream=True
    )
    for chunk in completion:
        if chunk.choices and chunk.choices[0].delta.content:
                text = chunk.choices[0].delta.content
                print(text, end="", flush=True)
                tts.speak(text)

        # 当前回答结束
        tts.flush()
    print()  # 流式输出结束后换行
    tts.stop()