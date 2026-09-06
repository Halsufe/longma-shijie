from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "frontend/js/views/overview.js").read_text(encoding="utf-8")


def test_overview_keeps_existing_data_contracts_and_navigation() -> None:
    for endpoint in (
        '/api/v1/notifications?page_size=5',
        '/api/v1/schedule/today',
        '/api/v1/assignments?status=published&page_size=5',
        '/api/v1/applications/plans/mine?page_size=5&is_completed=false',
        '/api/v1/recommendations/?limit=4',
        '/api/v1/achievements/stats',
        '/api/v1/admin/stats',
    ):
        assert endpoint in SOURCE
    assert 'context.navigate(node.dataset.go)' in SOURCE
    assert 'context.navigate("community", { view: "mine", category: node.dataset.achievementCategory })' in SOURCE


def test_overview_uses_shared_components_and_priority_layout() -> None:
    for token in ("pageHeader", "stats-grid", "content-grid", "panel", "quick-list", "emptyState", "loadingState", "statusBadge"):
        assert token in SOURCE
    assert SOURCE.index('section class="stats-grid"') < SOURCE.rindex('${achievementOverview(')
    assert SOURCE.rindex('${quickAccessPanel()}') < SOURCE.rindex('${aiPanel()}')
    assert SOURCE.rindex('${aiPanel()}') < SOURCE.rindex('${canViewParty ? partyPanel(')
    assert SOURCE.rindex('${canViewParty ? partyPanel(') < SOURCE.rindex('${notificationPanel(')
    assert "Promise.allSettled" in SOURCE


def test_overview_is_role_aware_and_does_not_fake_failed_counts() -> None:
    assert '["student", "admin"].includes(context.user.role)' in SOURCE
    assert 'context.user.role === "admin"' in SOURCE
    assert 'resultError(results, "achievements") || !achievementStats' in SOURCE
    assert 'unread_count: 0' not in SOURCE
    assert 'total: 0' not in SOURCE
    assert 'escapeHtml(item.title)' in SOURCE
    assert 'escapeHtml(item.name)' in SOURCE


def test_overview_removes_school_announcements_panel_and_request() -> None:
    assert "school-announcements" not in SOURCE
    assert "announcementPanel" not in SOURCE
    assert "学校公告" not in SOURCE
