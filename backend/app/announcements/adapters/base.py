from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Protocol
from urllib.parse import urljoin, urlsplit, urlunsplit


@dataclass(slots=True)
class AttachmentLink:
    name: str
    url: str
    media_type: str | None = None


@dataclass(slots=True)
class AnnouncementCandidate:
    title: str
    url: str
    published_at: date | datetime | None = None
    source_code: str = ""
    raw_date: str | None = None


@dataclass(slots=True)
class AnnouncementDocument:
    title: str
    url: str
    body: str
    published_at: date | datetime | None = None
    attachments: list[AttachmentLink] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass(slots=True)
class CrawlContext:
    now: datetime
    base_url: str = ""
    page: int = 1
    max_pages: int = 10
    seen_urls: set[str] = field(default_factory=set)


class AnnouncementSourceAdapter(Protocol):
    source_code: str

    async def list_candidates(self, context: CrawlContext) -> list[AnnouncementCandidate]: ...
    async def fetch_detail(self, candidate: AnnouncementCandidate) -> AnnouncementDocument: ...


def normalize_url(url: str, base_url: str | None = None) -> str:
    """Normalize links for idempotency without changing their meaning."""
    absolute = urljoin(base_url or "", (url or "").strip())
    parts = urlsplit(absolute)
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        raise ValueError("only absolute HTTP(S) URLs are supported")
    host = parts.hostname.lower() if parts.hostname else ""
    port = parts.port
    netloc = host
    if port and not ((parts.scheme.lower() == "http" and port == 80) or (parts.scheme.lower() == "https" and port == 443)):
        netloc = f"{host}:{port}"
    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), netloc, path, parts.query, ""))

