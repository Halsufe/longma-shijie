from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.app.services.chat_retrieval_service import ChatRetrievalService
from backend.app.services.web_search_service import WebSearchService


class PlannerAdapter:
    name = "generic:test"

    def __init__(self, responses: list[str]):
        self.responses = iter(responses)

    async def chat(self, messages, system_prompt=""):
        return next(self.responses)


@pytest.mark.asyncio
async def test_attachment_has_priority_and_stops_fallback(monkeypatch) -> None:
    adapter = PlannerAdapter([
        '{"sufficient": true, "web_needed": false, "search_query": ""}'
    ])
    monkeypatch.setattr(
        "backend.app.services.chat_retrieval_service.RAGService.search",
        lambda *args, **kwargs: pytest.fail("knowledge search must not run"),
    )
    monkeypatch.setattr(
        "backend.app.services.chat_retrieval_service.SystemSearchService.search",
        lambda *args, **kwargs: pytest.fail("system search must not run"),
    )
    monkeypatch.setattr(
        "backend.app.services.chat_retrieval_service.WebSearchService.search",
        lambda *args, **kwargs: pytest.fail("web search must not run"),
    )

    result = await ChatRetrievalService.retrieve(
        MagicMock(),
        query="请总结附件",
        user_id=1,
        rag_scope="all",
        attachment_context="[附件：notes.txt]\n附件正文",
        adapter=adapter,
    )

    assert "用户附件（最高优先级）" in result.prompt
    assert not result.knowledge_sources
    assert not result.system_sources
    assert not result.web_sources


@pytest.mark.asyncio
async def test_none_scope_skips_knowledge_and_uses_web_fallback(monkeypatch) -> None:
    adapter = PlannerAdapter([
        '{"sufficient": false, "web_needed": true, "search_query": "FastAPI 最新版本"}',
        '{"sufficient": true, "web_needed": false, "search_query": ""}',
    ])
    monkeypatch.setattr(
        "backend.app.services.chat_retrieval_service.RAGService.search",
        lambda *args, **kwargs: pytest.fail("none scope must not search knowledge"),
    )
    monkeypatch.setattr(
        "backend.app.services.chat_retrieval_service.SystemSearchService.search",
        lambda *args, **kwargs: [],
    )

    seen_queries: list[str] = []

    async def fake_web_search(query: str):
        seen_queries.append(query)
        return [{"title": "FastAPI", "url": "https://fastapi.tiangolo.com/", "snippet": "Latest documentation"}]

    monkeypatch.setattr(
        "backend.app.services.chat_retrieval_service.WebSearchService.search",
        fake_web_search,
    )

    result = await ChatRetrievalService.retrieve(
        MagicMock(),
        query="FastAPI 最新版本是什么？",
        user_id=1,
        rag_scope="none",
        attachment_context="",
        adapter=adapter,
    )

    assert seen_queries == ["FastAPI 最新版本"]
    assert result.web_sources == ["FastAPI"]
    assert "不得引用个人或班级知识库" in result.prompt
    assert result.citations[0]["source_type"] == "web"


@pytest.mark.asyncio
async def test_personal_scope_uses_local_result_without_web(monkeypatch) -> None:
    adapter = PlannerAdapter([
        '{"sufficient": true, "web_needed": false, "search_query": ""}'
    ])
    monkeypatch.setattr(
        "backend.app.services.chat_retrieval_service.RAGService.search",
        lambda *args, **kwargs: [{
            "file_id": 8,
            "file_name": "个人笔记.md",
            "chunk_content": "课程重点是数据库索引。",
            "page_no": None,
            "score": 1.0,
        }],
    )
    monkeypatch.setattr(
        "backend.app.services.chat_retrieval_service.SystemSearchService.search",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        "backend.app.services.chat_retrieval_service.WebSearchService.search",
        lambda *args, **kwargs: pytest.fail("web search must not run"),
    )

    result = await ChatRetrievalService.retrieve(
        MagicMock(),
        query="课程重点是什么？",
        user_id=1,
        rag_scope="personal",
        attachment_context="",
        adapter=adapter,
    )

    assert result.knowledge_sources == ["个人笔记.md"]
    assert not result.web_sources
    assert result.citations[0]["source_type"] == "knowledge"


@pytest.mark.asyncio
async def test_structured_web_result_stops_before_general_search(monkeypatch) -> None:
    structured = {
        "title": "PyPI：fastapi 0.141.1",
        "url": "https://pypi.org/project/fastapi/",
        "snippet": "当前发布版本：0.141.1",
        "content": "当前发布版本：0.141.1",
    }

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def get(self, *args, **kwargs):
            pytest.fail("general search must stop after a structured result")

    async def fake_pypi(cls, client, query):
        return structured

    monkeypatch.setattr(
        "backend.app.services.web_search_service.httpx.AsyncClient",
        lambda **kwargs: FakeClient(),
    )
    monkeypatch.setattr(WebSearchService, "_pypi_result", classmethod(fake_pypi))

    assert await WebSearchService.search("FastAPI latest stable version") == [structured]
