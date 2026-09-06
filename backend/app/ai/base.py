from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional


class AIAdapter(ABC):
    """AI 模型适配器抽象基类"""

    @abstractmethod
    def chat_stream(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """流式返回 AI 回复片段"""
        ...

    @abstractmethod
    async def chat(self, messages: list[dict], system_prompt: Optional[str] = None, **kwargs) -> str:
        """非流式返回完整回复"""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...


# 全局单例
_adapter: Optional[AIAdapter] = None


def get_adapter() -> AIAdapter:
    global _adapter
    if _adapter is None:
        from backend.app.core.config import settings

        if settings.AI_API_KEY and settings.AI_BASE_URL:
            from backend.app.ai.generic_adapter import GenericAdapter
            # The product keeps a stable internal model id for analytics and
            # quota records, while providers receive their configured model id.
            provider_model = settings.AI_MODEL or "deepseek-chat"
            if provider_model == "deepseek-v4-flash":
                provider_model = "deepseek-chat"
            _adapter = GenericAdapter(
                base_url=settings.AI_BASE_URL,
                api_key=settings.AI_API_KEY,
                model=provider_model,
            )
        else:
            from backend.app.ai.mock_adapter import MockAdapter
            _adapter = MockAdapter()
    return _adapter


def reset_adapter() -> None:
    global _adapter
    _adapter = None
