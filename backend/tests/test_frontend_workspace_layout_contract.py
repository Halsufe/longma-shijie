from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MENTOR = (ROOT / "frontend/js/mentor_selection.js").read_text(encoding="utf-8")
PARTY = (ROOT / "frontend/js/views/party.js").read_text(encoding="utf-8")
STYLES = (ROOT / "frontend/assets/styles.css").read_text(encoding="utf-8")


def test_mentor_workbench_exposes_summary_main_and_side_regions() -> None:
    assert "mentor-workbench" in MENTOR
    assert "mentor-summary-grid" in MENTOR
    assert "mentor-main-panel" in MENTOR
    assert "mentor-side-panel" in MENTOR
    assert "data-rank=" in MENTOR
    assert "ms-submit" in MENTOR


def test_party_workbench_exposes_summary_activity_and_support_regions() -> None:
    assert "party-workbench" in PARTY
    assert "party-summary-grid" in PARTY
    assert "party-activity-list" in PARTY
    assert "party-support-rail" in PARTY
    assert "data-party-register" in PARTY
    assert "data-party-signin" in PARTY


def test_workbench_layout_has_desktop_and_mobile_rules() -> None:
    for token in (
        ".mentor-workbench",
        ".mentor-main-panel",
        ".mentor-side-panel",
        ".party-workbench",
        ".party-support-rail",
    ):
        assert token in STYLES
    assert "@media (max-width: 860px)" in STYLES
    assert "@media (max-width: 760px)" in STYLES
