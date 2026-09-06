from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_chat_composer_stays_inside_short_viewports() -> None:
    styles = (PROJECT_ROOT / "frontend" / "assets" / "styles.css").read_text(
        encoding="utf-8"
    )
    index = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")

    assert ".chat-layout" in styles
    assert "height: calc(100dvh - var(--header-height) - 84px)" in styles
    assert "height: calc(100dvh - var(--header-height) - 72px)" in styles
    assert "grid-template-rows: minmax(0, 1fr)" in styles
    assert "grid-template-rows: auto minmax(0, 1fr) auto" in styles
    assert ".chat-sidebar" in styles and "min-height: 0; overflow: hidden" in styles
    assert ".session-list { flex: 1 1 auto; min-height: 0" in styles
    assert "min-height: 580px" not in styles
    assert "styles.css?v=" in index
