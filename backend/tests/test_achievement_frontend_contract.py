from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_JS = PROJECT_ROOT / "frontend" / "js"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_dynamic_form_uses_registry_and_covers_required_validation_rules() -> None:
    source = read(FRONTEND_JS / "achievement_form.js")

    assert "ACHIEVEMENT_TEMPLATES" in source
    assert "ACHIEVEMENT_CATEGORIES.map" in source
    assert "renderAchievementTemplate" in source
    assert "validateAchievementForm" in source
    assert 'field.type === "bool"' in source
    assert 'field.type === "select"' in source
    assert 'field.type === "textarea"' in source
    for rule in (
        "year:1900-current",
        "month:1-12",
        "decimal-2|无",
        "page-range|forthcoming",
        "name-list:comma-separated-no-empty-items",
        "new URL(text)",
    ):
        assert rule in source
    assert "data-error-for" in source
    assert "旧版成果记录" in source


def test_attachment_component_matches_authenticated_file_api_contract() -> None:
    source = read(FRONTEND_JS / "achievement_upload.js")

    assert "application/pdf" in source
    assert "image/jpeg" in source
    assert "image/png" in source
    assert "multiple data-proof-input" in source
    assert "data-preview-proof" in source
    assert "data-remove-proof" in source
    assert "data-replace-proof" in source
    assert 'body.append("file"' in source
    assert 'uploadApi("/api/v1/achievements/files"' in source
    assert "Authorization" in source
    assert "openAchievementProof" in source
    assert "请至少上传1份证明材料" in source


def test_community_integrates_timeline_list_crud_and_template_payloads() -> None:
    source = read(FRONTEND_JS / "views" / "community.js")

    assert 'from "../achievement_timeline.js"' in source
    assert 'from "../achievement_list.js?v=20260807-achievement-groups"' in source
    assert 'api("/api/v1/achievements/years")' in source
    assert "renderAchievementTimeline" in source
    assert "renderAchievementList" in source
    assert 'method: "POST"' in source
    assert 'method: "PUT"' in source
    assert 'method: "DELETE"' in source
    assert "details" in source
    assert "proofs" in source
    assert "资源社区" in source
    assert "我的成果" in source
    assert "成果广场" in source
    assert "renderAchievementDetail" in source


def test_my_achievements_render_all_eight_category_groups_for_every_year_view() -> None:
    community = read(FRONTEND_JS / "views" / "community.js")
    achievement_list = read(FRONTEND_JS / "achievement_list.js")

    assert "renderAchievementCategoryGroups" in community
    assert 'year: selectedYear' in community
    assert 'selectedYear = null' in community
    assert 'data-add-achievement-category' in community
    assert "ACHIEVEMENT_CATEGORIES.map" in achievement_list
    assert 'aria-label="八类成果"' in achievement_list
    assert 'data-achievement-category-group' in achievement_list
    assert 'achievement-category-count' in achievement_list
    for category in ("paper", "award", "research", "patent", "innovation", "organization", "social", "arts"):
        assert f'{category}:' in achievement_list


def test_achievement_styles_include_responsive_form_and_attachment_layouts() -> None:
    source = read(PROJECT_ROOT / "frontend" / "assets" / "styles.css")

    assert ".achievement-fields-grid" in source
    assert ".achievement-proof-item" in source
    assert ".achievement-detail-grid" in source
    assert "@media (max-width: 620px)" in source
    assert ".achievement-fields-grid { grid-template-columns: 1fr; }" in source
    assert ".achievement-category-groups" in source
    assert ".achievement-category-section" in source
    assert ".achievement-category-count" in source


def test_avatar_and_framed_icons_keep_centering_layout() -> None:
    source = read(PROJECT_ROOT / "frontend" / "assets" / "styles.css")

    assert ".user-mini > div strong, .user-mini > div span" in source
    assert ".quick-item .quick-item-icon { display: grid; place-items: center;" in source
    assert "flex: 0 0 34px" in source
    assert ".table-title > span:not(.avatar):not(.quick-item-icon)" in source
