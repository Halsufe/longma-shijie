import json
import logging
from typing import AsyncGenerator, Optional

import httpx

from backend.app.ai.base import AIAdapter

logger = logging.getLogger(__name__)


class AIProviderError(RuntimeError):
    """A provider request failed after the bounded retry policy."""

    code = "AI_PROVIDER_UNAVAILABLE"


class GenericAdapter(AIAdapter):
    """兼容 OpenAI 格式的通用 AI 适配器

    特性：
    - 流式输出支持断线重连（最多重试 2 次）
    - 分离的连接/读取超时设置
    - 友好的中文错误提示
    """

    # 流式请求最大重试次数
    MAX_RETRIES = 2

    def __init__(self, base_url: str, api_key: str, model: str = "gpt-3.5-turbo"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.last_usage: dict | None = None
        self.last_attempt_count = 0

    @property
    def name(self) -> str:
        return f"generic:{self.model}"

    def _build_payload(
        self, messages: list[dict], system_prompt: Optional[str], stream: bool = False
    ) -> dict:
        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        payload = {
            "model": self.model,
            "messages": full_messages,
            "stream": stream,
            "temperature": 0.7,
        }
        if stream:
            payload["stream_options"] = {"include_usage": True}
        return payload

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _get_timeout(self) -> httpx.Timeout:
        """分离的超时设置：连接快超时，读取慢超时"""
        return httpx.Timeout(
            connect=10.0,      # 连接超时 10 秒
            read=120.0,        # 读取超时 120 秒（流式响应可能较慢）
            write=10.0,        # 发送超时 10 秒
            pool=5.0,          # 连接池超时 5 秒
        )

    async def chat_stream(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """流式对话，支持断线重连"""
        self.last_usage = None
        self.last_attempt_count = 0
        payload = self._build_payload(messages, system_prompt, stream=True)
        headers = self._get_headers()
        url = f"{self.base_url}/chat/completions"
        timeout = self._get_timeout()

        last_error = None
        for attempt in range(1, self.MAX_RETRIES + 2):  # 1次正常 + 2次重试
            self.last_attempt_count = attempt
            try:
                got_content = False
                async with httpx.AsyncClient(timeout=timeout) as client:
                    async with client.stream("POST", url, json=payload, headers=headers) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if not line or not line.startswith("data: "):
                                continue
                            data = line[len("data: "):]
                            if data.strip() == "[DONE]":
                                return
                            try:
                                chunk = json.loads(data)
                                usage = chunk.get("usage")
                                if isinstance(usage, dict):
                                    self.last_usage = usage
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                content = delta.get("content")
                                if content:
                                    got_content = True
                                    yield content
                            except json.JSONDecodeError:
                                continue
                # 正常完成
                return

            except httpx.HTTPError as e:
                last_error = e
                error_msg = str(e)
                logger.warning(
                    "AI stream attempt %d/%d failed: %s",
                    attempt, self.MAX_RETRIES + 1, error_msg
                )

                # 如果已经输出了部分内容，不再重试（避免重复输出）
                if got_content:
                    yield "\n\n⚠️ [AI 连接中断，以上为部分回复。请重新发送消息以获取完整回复。]"
                    return

                # 如果还有重试机会，继续
                if attempt <= self.MAX_RETRIES:
                    logger.info("Retrying AI stream (attempt %d)...", attempt + 1)
                    continue

                # 重试耗尽，交给编排层生成真正的 failed 事件；不要把
                # 错误文本伪装成正常 chunk，否则请求会被错误标记为完成。
                friendly_msg = self._friendly_error(e)
                raise AIProviderError(friendly_msg) from e

    def _friendly_error(self, e: Exception) -> str:
        """将技术性错误转换为用户友好的中文提示"""
        error_str = str(e)
        error_type = type(e).__name__

        if "incomplete chunked read" in error_str or "peer closed" in error_str:
            return "AI 服务器中断了连接，请稍后重试"
        if "timeout" in error_str.lower() or "timed out" in error_str.lower():
            return "AI 响应超时，请稍后重试"
        if "connect" in error_str.lower() or "connection" in error_str.lower():
            return "无法连接到 AI 服务器，请检查网络"
        if "401" in error_str or "unauthorized" in error_str.lower():
            return "AI API 密钥无效"
        if "429" in error_str or "rate" in error_str.lower():
            return "AI 请求频率过高，请稍后重试"
        if "500" in error_str or "502" in error_str or "503" in error_str:
            return "AI 服务器内部错误，请稍后重试"

        # 兜底：返回简短的错误类型
        short_msg = error_str[:100] if error_str else error_type
        return f"{error_type}: {short_msg}"

    async def chat(self, messages: list[dict], system_prompt: Optional[str] = None, **kwargs) -> str:
        """非流式对话，支持重试"""
        self.last_usage = None
        self.last_attempt_count = 0
        payload = self._build_payload(messages, system_prompt, stream=False)
        headers = self._get_headers()
        url = f"{self.base_url}/chat/completions"
        timeout = self._get_timeout()

        last_error = None
        for attempt in range(1, self.MAX_RETRIES + 2):
            self.last_attempt_count = attempt
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(url, json=payload, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                    usage = data.get("usage")
                    self.last_usage = usage if isinstance(usage, dict) else None
                    return data.get("choices", [{}])[0].get("message", {}).get("content", "")
            except httpx.HTTPError as e:
                last_error = e
                logger.warning(
                    "AI request attempt %d/%d failed: %s",
                    attempt, self.MAX_RETRIES + 1, str(e)
                )
                if attempt <= self.MAX_RETRIES:
                    logger.info("Retrying AI request (attempt %d)...", attempt + 1)
                    continue
                friendly_msg = self._friendly_error(e)
                # Non-stream callers (business Skills and the retrieval
                # planner) historically consume a text response. Keep that
                # compatibility; the user-facing SSE path raises above.
                return f"[AI 请求失败: {friendly_msg}]"

        return f"[AI 请求失败: {self._friendly_error(last_error or RuntimeError('未知错误'))}]"
