import httpx
import pytest

from backend.app.ai.generic_adapter import AIProviderError, GenericAdapter
from backend.app.ai import base as ai_base


class FailingStream:
    async def __aenter__(self):
        raise httpx.ConnectError("All connection attempts failed")

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FailingClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    def stream(self, *args, **kwargs):
        return FailingStream()


class UsageResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8},
        }


class UsageClient(FailingClient):
    async def post(self, *args, **kwargs):
        return UsageResponse()


@pytest.mark.asyncio
async def test_stream_connection_failure_returns_friendly_error(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FailingClient())
    adapter = GenericAdapter(
        base_url="https://api.deepseek.com",
        api_key="test-key",
        model="deepseek-chat",
    )

    with pytest.raises(AIProviderError, match="无法连接到 AI 服务器"):
        _ = [chunk async for chunk in adapter.chat_stream([{"role": "user", "content": "你好"}])]
    assert adapter.last_attempt_count == 3


@pytest.mark.asyncio
async def test_non_stream_usage_is_exposed_for_quota_settlement(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: UsageClient())
    adapter = GenericAdapter(
        base_url="https://api.deepseek.com",
        api_key="test-key",
        model="deepseek-v4-flash",
    )

    assert await adapter.chat([{"role": "user", "content": "hello"}]) == "ok"
    assert adapter.last_usage == {
        "prompt_tokens": 3,
        "completion_tokens": 5,
        "total_tokens": 8,
    }
    assert adapter._build_payload([], None, stream=True)["stream_options"] == {
        "include_usage": True
    }


def test_adapter_factory_maps_legacy_product_model_to_deepseek_chat(monkeypatch):
    class FakeSettings:
        AI_API_KEY = "test-key"
        AI_BASE_URL = "https://api.deepseek.com"
        AI_MODEL = "deepseek-v4-flash"

    monkeypatch.setattr("backend.app.core.config.settings", FakeSettings())
    ai_base.reset_adapter()
    adapter = ai_base.get_adapter()
    assert isinstance(adapter, GenericAdapter)
    assert adapter.model == "deepseek-chat"
    ai_base.reset_adapter()
