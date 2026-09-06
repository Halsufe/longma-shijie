from datetime import date, datetime

import pytest

from backend.app.announcements.adapters.base import normalize_url
from backend.app.announcements.adapters.html_adapter import GenericHtmlAdapter
from backend.app.announcements.security import FetchSecurityError, validate_url
from backend.app.models.announcement import SchoolAnnouncement


def test_normalize_url_removes_fragment_and_default_port():
    assert normalize_url("HTTPS://Example.COM:443/path/#section") == "https://example.com/path"


def test_ssrf_rejects_private_address():
    with pytest.raises(FetchSecurityError):
        validate_url("http://127.0.0.1/internal")


@pytest.mark.asyncio
async def test_html_adapter_isolates_candidates_and_attachments():
    adapter = GenericHtmlAdapter("demo", "https://example.edu/")
    candidates = await adapter.list_candidates(type("C", (), {})(), '<a href="/a.html">重要通知</a><a href="javascript:bad">忽略</a>')
    assert len(candidates) == 1
    document = await adapter.fetch_detail(candidates[0], '<article><h1>重要通知</h1><p>请于 2026-08-13 办理。</p><a href="/notice.pdf">附件</a></article>')
    assert "办理" in document.body
    assert document.attachments[0].url.endswith("/notice.pdf")


def test_retention_boundary_is_inclusive():
    item = SchoolAnnouncement(title="x", published_at=date(2026, 1, 1), retention_until=date(2026, 1, 31), status="ready", relevance_status="relevant")
    assert item.is_visible(date(2026, 1, 31))
    assert not item.is_visible(date(2026, 2, 1))
