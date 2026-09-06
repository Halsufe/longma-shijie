from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
VIEWS = PROJECT_ROOT / "frontend" / "js" / "views"


def _read(name: str) -> str:
    return (VIEWS / name).read_text(encoding="utf-8")


def test_business_views_keep_shared_layout_and_safe_text_helpers() -> None:
    for name in ("knowledge.js", "courses.js", "community.js", "mentorship.js", "party.js", "notifications.js", "profile.js", "admin.js"):
        source = _read(name)
        assert "pageHeader(" in source, name
        assert "loadingState" in source, name
        assert "emptyState" in source, name
        assert "escapeHtml" in source, name
        assert "fetch(" not in source, name


def test_chat_view_has_mobile_drawer_and_message_overflow_hooks() -> None:
    source = _read("chat.js")
    assert "chat-sidebar" in source
    assert "chat-drawer-scrim" in source
    assert "chat-close" in source
    assert "chat-menu" in source
    assert "streamChat(currentSession.id, payload" in source
    assert "escapeHtml(message.content)" in source


def test_mentorship_and_party_stay_as_separate_page_views() -> None:
    mentorship = _read("mentorship.js")
    party = _read("party.js")

    assert "renderMentorSelection" in mentorship
    assert "renderParty" in party
    assert "party-workbench" in party
    assert "mentor-workbench" in mentorship or "mentor-workbench" in (PROJECT_ROOT / "frontend/js/mentor_selection.js").read_text(encoding="utf-8")


def test_preview_helpers_stay_inside_authenticated_api_boundary() -> None:
    for relative in ("js/views/admin.js", "js/views/courses.js", "js/achievement_upload.js"):
        source = (PROJECT_ROOT / "frontend" / relative).read_text(encoding="utf-8")
        assert "fetchBlob" in source
        assert "fetch(" not in source
