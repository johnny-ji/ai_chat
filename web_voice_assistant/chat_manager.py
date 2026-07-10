"""chat_manager.py - 对话管理模块，处理 LLM 流式调用"""
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
        """流式对话生成"""
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
