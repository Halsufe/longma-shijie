from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _source() -> str:
    return (PROJECT_ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")


def test_app_shell_uses院徽_and_confirmed_brand_copy() -> None:
    source = _source()
    assert "/static/assets/院徽.jpg" in source
    assert "龙马·视界" in source
    assert "中央财经大学管理科学与工程学院" in source
    assert "大数据管理与应用" in source
    assert "brand-mark.svg" not in source
    assert "brand-stats" not in source


def test_app_shell_keeps_routes_and_mobile_drawer_accessibility() -> None:
    source = _source()
    for route in ("overview", "chat", "knowledge", "courses", "community", "mentorship", "notifications", "profile", "admin"):
        assert f"{route}: {{" in source
    assert 'aria-controls="app-sidebar"' in source
    assert 'aria-expanded="${state.sidebarOpen}"' in source
    assert 'event.key === "Escape"' in source
    assert "document.body.classList.add(\"drawer-open\")" in source
    assert "document.removeEventListener(\"keydown\", onShellKeydown)" in source


def test_app_shell_removes_school_announcements_route() -> None:
    source = _source()

    assert "renderAnnouncements" not in source
    assert "announcements:" not in source


def test_pending_password_change_uses_a_persistent_gate_instead_of_a_closable_modal() -> None:
    source = _source()

    assert "function renderRequiredPasswordChange()" in source
    assert 'app.querySelector("#required-password-form")' in source
    assert 'if (state.user.status === "pending_change")' in source
    assert "showRequiredPasswordChange" not in source
