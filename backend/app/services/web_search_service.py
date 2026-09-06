from __future__ import annotations

import asyncio
from html.parser import HTMLParser
import ipaddress
import logging
import re
import socket
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urlparse

import httpx

from backend.app.core.config import settings


logger = logging.getLogger(__name__)


class _PageTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self.ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self.ignored_depth:
            self.ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.ignored_depth and data.strip():
            self.parts.append(data.strip())

    def text(self) -> str:
        return " ".join(" ".join(self.parts).split())


class WebSearchService:
    """Small, keyless web-search adapter backed by Bing's RSS endpoint."""

    _VERSION_WORDS = ("version", "release", "latest", "版本", "最新版", "稳定版")
    _PACKAGE_STOP_WORDS = {
        "current", "latest", "stable", "version", "release", "what", "is",
        "the", "please", "find", "official", "documentation", "pypi",
    }

    @classmethod
    async def _pypi_result(
        cls, client: httpx.AsyncClient, query: str
    ) -> dict[str, str] | None:
        lowered = query.casefold()
        if not any(word in lowered for word in cls._VERSION_WORDS):
            return None
        candidates = [
            token
            for token in re.findall(r"[A-Za-z][A-Za-z0-9_.-]{1,60}", query)
            if token.casefold() not in cls._PACKAGE_STOP_WORDS
        ]
        for package in candidates[:3]:
            try:
                response = await client.get(f"https://pypi.org/pypi/{package}/json")
                if response.status_code == 404:
                    continue
                response.raise_for_status()
                data = response.json()
                info = data.get("info") or {}
                version = str(info.get("version") or "").strip()
                name = str(info.get("name") or package).strip()
                if not version:
                    continue
                url = str(
                    info.get("package_url")
                    or f"https://pypi.org/project/{package}/"
                )
                summary = str(info.get("summary") or "").strip()
                content = (
                    f"PyPI 项目名称：{name}；当前发布版本：{version}；"
                    f"项目摘要：{summary or '无'}；查询来源：PyPI JSON API。"
                )
                return {
                    "title": f"PyPI：{name} {version}",
                    "url": url,
                    "snippet": content,
                    "content": content,
                }
            except (httpx.HTTPError, ValueError, TypeError):
                continue
        return None

    @staticmethod
    async def _is_public_url(url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        try:
            addresses = await asyncio.to_thread(
                socket.getaddrinfo,
                parsed.hostname,
                parsed.port or (443 if parsed.scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            )
        except socket.gaierror:
            return False
        return bool(addresses) and all(
            ipaddress.ip_address(address[4][0]).is_global for address in addresses
        )

    @classmethod
    async def _page_text(
        cls, client: httpx.AsyncClient, url: str
    ) -> str:
        if not await cls._is_public_url(url):
            return ""
        try:
            response = await client.get(url)
            response.raise_for_status()
            for history_item in response.history:
                if not await cls._is_public_url(str(history_item.url)):
                    return ""
            if not await cls._is_public_url(str(response.url)):
                return ""
            content_type = response.headers.get("content-type", "").lower()
            if "html" not in content_type and "text/plain" not in content_type:
                return ""
            if len(response.content) > 2 * 1024 * 1024:
                return ""
            parser = _PageTextExtractor()
            parser.feed(response.text)
            return parser.text()[:5000]
        except (httpx.HTTPError, ValueError):
            return ""

    @staticmethod
    async def search(query: str, limit: int | None = None) -> list[dict[str, str]]:
        if not settings.WEB_SEARCH_ENABLED:
            return []
        clean_query = " ".join(query.split())[:500]
        if not clean_query:
            return []
        result_limit = min(max(limit or settings.WEB_SEARCH_MAX_RESULTS, 1), 10)
        try:
            async with httpx.AsyncClient(
                timeout=settings.WEB_SEARCH_TIMEOUT_SECONDS,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; LongmaBot/1.0)"},
            ) as client:
                structured = await WebSearchService._pypi_result(client, clean_query)
                if structured:
                    logger.info(
                        "Structured web lookup: query=%r source=PyPI",
                        clean_query[:80],
                    )
                    return [structured]
                response = await client.get(
                    settings.WEB_SEARCH_URL,
                    params={"format": "rss", "q": clean_query},
                )
                response.raise_for_status()
                root = ET.fromstring(response.content)

                results: list[dict[str, str]] = []
                if structured:
                    results.append(structured)
                for xml_item in root.findall("./channel/item"):
                    title = (xml_item.findtext("title") or "").strip()
                    url = (xml_item.findtext("link") or "").strip()
                    snippet = (xml_item.findtext("description") or "").strip()
                    if not title or not url or any(row["url"] == url for row in results):
                        continue
                    results.append({"title": title, "url": url, "snippet": snippet[:1200]})
                    if len(results) >= result_limit:
                        break

                enrichable = [result_item for result_item in results if not result_item.get("content")][:2]
                page_contents = await asyncio.gather(
                    *(WebSearchService._page_text(client, result_item["url"]) for result_item in enrichable)
                )
                for result_item, content in zip(enrichable, page_contents):
                    if content:
                        result_item["content"] = content
        except (httpx.HTTPError, ET.ParseError, ValueError) as exc:
            logger.warning("Web search failed for query=%r: %s", clean_query[:80], exc)
            return []
        logger.info("Web search: query=%r results=%d", clean_query[:80], len(results))
        return results

    @staticmethod
    def build_context(results: list[dict[str, str]]) -> str:
        parts = []
        for index, item in enumerate(results, 1):
            parts.append(
                f"[网页{index}] {item['title']}\n"
                f"网址：{item['url']}\n摘要：{item.get('snippet') or '无摘要'}\n"
                f"页面正文：{item.get('content') or '未抓取到正文'}"
            )
        return "\n\n".join(parts)

    @staticmethod
    def citations(results: list[dict[str, str]]) -> list[dict[str, Any]]:
        return [
            {
                "name": item["title"],
                "url": item["url"],
                "preview": (item.get("snippet") or item.get("content") or "")[:200],
                "source_type": "web",
            }
            for item in results
        ]
