import asyncio
import time
import random

from typing import AsyncGenerator, Optional

from backend.app.ai.base import AIAdapter


class MockAdapter(AIAdapter):
    """模拟 AI 适配器，用于开发和测试"""

    @property
    def name(self) -> str:
        return "mock"

    async def chat_stream(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        last_user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user_msg = m.get("content", "")
                break

        if not last_user_msg:
            response = "你好，我是龙马·视界的 AI 助手（模拟模式）。请问有什么可以帮您？"
        else:
            response = (
                f"【模拟回复】\n\n收到您的消息：{last_user_msg}\n\n"
                f"当前为开发环境模拟回复。配置 AI_API_KEY 和 AI_BASE_URL 后可接入真实大模型。\n\n"
                f"如果您看到这条消息，说明对话流式返回正常工作。"
            )

        # 按字符流式输出
        for char in response:
            yield char
            await asyncio.sleep(0.02)

    async def chat(self, messages: list[dict], system_prompt: Optional[str] = None, **kwargs) -> str:
        result = ""
        async for chunk in self.chat_stream(messages, system_prompt, **kwargs):
            result += chunk
        return result