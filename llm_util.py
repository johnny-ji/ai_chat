import os
from openai import OpenAI



def chat_with_streaming_response(user_message: str):
    """
    使用流式响应进行聊天。
    """

    client = OpenAI(
        # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key="sk-xxx",
        api_key="sk-5161496c3b6a4690b7a6c4a075a74181",
        base_url="https://ws-pfc9xcvzdopof45u.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
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
        print(chunk.choices[0].delta.content, end="", flush=True)