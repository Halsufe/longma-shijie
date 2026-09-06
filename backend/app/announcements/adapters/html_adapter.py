from __future__ import annotations

import re
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin

from backend.app.announcements.adapters.base import (
    AnnouncementCandidate,
    AnnouncementDocument,
    AttachmentLink,
    CrawlContext,
    normalize_url,
)


DATE_RE = re.compile(r"(20\d{2})[年./-](\d{1,2})[月./-](\d{1,2})")


def _parse_date(text: str | None):
    if not text:
        return None
    match = DATE_RE.search(text)
    if not match:
        return None
    try:
        return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3))).date()
    except ValueError:
        return None


class _LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href = ""
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            self._href = dict(attrs).get("href", "")
            self._text = []

    def handle_data(self, data):
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href:
            self.links.append((self._href, " ".join("".join(self._text).split())))
            self._href, self._text = "", []


class GenericHtmlAdapter:
    """Offline-friendly adapter for common Chinese announcement list/detail HTML."""

    def __init__(self, source_code: str, base_url: str, list_url: str = ""):
        self.source_code = source_code
        self.base_url = base_url
        self.list_url = list_url or base_url

    async def list_candidates(self, context: CrawlContext, html: str | None = None) -> list[AnnouncementCandidate]:
        if html is None:
            return []
        parser = _LinkParser()
        parser.feed(html)
        result: list[AnnouncementCandidate] = []
        for href, title in parser.links:
            if len(title) < 2:
                continue
            try:
                url = normalize_url(urljoin(self.base_url, href))
            except ValueError:
                continue
            published = _parse_date(title)
            result.append(AnnouncementCandidate(title, url, published, self.source_code, title))
        return result

    async def fetch_detail(self, candidate: AnnouncementCandidate, html: str | None = None) -> AnnouncementDocument:
        if html is None:
            return AnnouncementDocument(candidate.title, candidate.url, "", candidate.published_at)
        parser = _LinkParser()
        parser.feed(html)
        cleaned = re.sub(r"<script[^>]*>.*?</script>|<style[^>]*>.*?</style>", " ", html, flags=re.I | re.S)
        body = "\n".join(line.strip() for line in re.sub(r"<[^>]+>", "\n", cleaned).splitlines() if line.strip())
        attachments: list[AttachmentLink] = []
        for href_raw, link_text in parser.links:
            try:
                href = normalize_url(urljoin(candidate.url, href_raw))
            except ValueError:
                continue
            name = link_text or href.rsplit("/", 1)[-1]
            attachments.append(AttachmentLink(name=name, url=href))
        return AnnouncementDocument(candidate.title, candidate.url, unescape(body), candidate.published_at, attachments)
