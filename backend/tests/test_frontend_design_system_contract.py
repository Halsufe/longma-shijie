from pathlib import Path
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STYLES = PROJECT_ROOT / "frontend" / "assets" / "styles.css"
UI_JS = PROJECT_ROOT / "frontend" / "js" / "ui.js"


def test_design_tokens_and_shared_component_states_are_defined() -> None:
    source = STYLES.read_text(encoding="utf-8")

    for token in (
        "--brand-900: #10243f",
        "--brand-700: #204b7a",
        "--brand-500: #577fa2",
        "--gold-500: #c5a451",
        "--bg: #f6f4ee",
        "--font-display:",
        "--font-body:",
        "--success:",
        "--warning:",
        "--danger:",
        "--focus-ring:",
        "--content-max-width: 1440px",
        "--shadow-float:",
    ):
        assert token in source

    for selector in (
        ".button[aria-busy=\"true\"]",
        ".button.is-error",
        ".icon-button:focus-visible",
        ".input[aria-invalid=\"true\"]",
        ".select:disabled",
        ".panel.is-loading",
        ".panel.is-error",
        ".data-table tbody tr:focus-within",
        ".badge-dot",
        ".toast-marker",
        ".modal-error",
    ):
        assert selector in source


def test_shell_breakpoints_and_emblem_containment_are_protected() -> None:
    source = STYLES.read_text(encoding="utf-8")

    for selector in (
        ".sidebar {",
        ".topbar {",
        ".main-content {",
        ".sidebar-scrim {",
        ".content-grid {",
    ):
        assert selector in source
    assert ".brand-lockup img, .sidebar-brand img, .brand-emblem, .school-emblem" in source
    assert "object-fit: contain" in source
    assert "html { min-width: 320px" in source
    for breakpoint in (1200, 860, 620, 320):
        assert f"@media (max-width: {breakpoint}px)" in source


def test_ui_helpers_keep_compatible_markup_and_accessible_hooks() -> None:
    script = r'''
const ui = await import("./frontend/js/ui.js?design-system-contract");
const badge = ui.statusBadge("approved");
if (!badge.includes("badge-success") || !badge.includes("badge-dot") || !badge.includes("已通过")) throw new Error("badge hooks missing");
const unknownBadge = ui.statusBadge('<unsafe>');
if (unknownBadge.includes('<unsafe>') || !unknownBadge.includes('&lt;unsafe&gt;')) throw new Error("badge escaping regressed");
const loading = ui.loadingState("读取中");
if (!loading.includes('data-state="loading"') || !loading.includes('role="status"')) throw new Error("loading semantics missing");
const empty = ui.emptyState("暂无", "稍后再试");
if (!empty.includes('data-state="empty"') || !empty.includes('state-empty')) throw new Error("empty semantics missing");
const header = ui.pageHeader("标题", "说明", '<button>操作</button>');
if (!header.includes('data-ui="page-header"') || !header.includes('class="page-heading"')) throw new Error("header hooks missing");
'''
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout

    source = UI_JS.read_text(encoding="utf-8")
    for hook in (
        'title="关闭弹窗"',
        'role="alert"',
        'aria-live',
        'button.setAttribute("aria-busy", "true")',
        'event.key === "Escape"',
        'event.key !== "Tab"',
        'previouslyFocused?.focus?.()',
    ):
        assert hook in source
