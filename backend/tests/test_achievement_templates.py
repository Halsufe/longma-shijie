import pytest

from backend.app.services.achievement_templates import (
    ACHIEVEMENT_TEMPLATES,
    ARTS_LEVEL_OPTIONS,
    STANDARD_LEVEL_OPTIONS,
    derive_achievement_date,
    derive_year,
    serialize_templates,
)


EXPECTED_DETAIL_KEYS = {
    "paper": {
        "authors", "journal", "sci_indexed", "ssci_indexed", "cssci_indexed",
        "is_top_journal", "paper_type", "pub_year", "pub_month", "wos_url",
        "volume", "issue", "citation_count", "research_direction", "pages",
        "keywords", "doi", "abstract",
    },
    "award": {
        "award_grade", "organizer", "award_year", "award_month", "teacher_names",
        "is_team", "is_leader", "member_names", "description",
    },
    "research": {
        "project_unit", "project_field", "project_funding", "leader_name",
        "participant_names", "project_year", "start_year", "start_month",
        "end_year", "end_month", "approval_no",
    },
    "patent": {
        "patent_type", "participant_names", "field", "apply_year", "apply_month",
        "grant_year", "grant_month", "application_no", "grant_no", "abstract",
    },
    "innovation": {
        "project_category", "leader_name", "member_names", "teacher_names",
        "start_year", "start_month", "end_year", "end_month", "summary",
    },
    "organization": {
        "position", "assessment", "honor_title", "start_year", "start_month",
        "end_year", "end_month",
    },
    "social": {
        "practice_unit", "is_team", "member_names", "is_leader", "start_year",
        "start_month", "end_year", "end_month", "process_description",
    },
    "arts": {
        "organizer", "start_year", "start_month", "end_year", "end_month", "summary",
    },
}


EXPECTED_TITLE_COPY = {
    "paper": "以下是您的学术论文，您可以修改和新增。所有条目必填",
    "award": "以下是您的竞赛获奖记录，您可以修改和新增。所有条目必填",
    "research": "以下是您的项目课题记录，您可以修改和新增。所有条目必填",
    "patent": "以下是您的专利/软著记录，您可以修改和新增。所有条目必填",
    "innovation": "以下是您的创新创业项目列表，您可以查看、修改或新增。所有条目必填",
    "organization": "以下是您的组织或部门任职经历信息，您可以修改和新增。所有条目必填",
    "social": "以下是您的社会实践信息，您可以修改和新增。所有条目必填",
    "arts": "以下是您的文体活动信息，您可以修改和新增。所有条目必填",
}


def field_map(category):
    return {field.key: field for field in ACHIEVEMENT_TEMPLATES[category].fields}


def test_registry_contains_all_eight_categories_and_exact_detail_fields():
    assert set(ACHIEVEMENT_TEMPLATES) == set(EXPECTED_DETAIL_KEYS)
    for category, expected_keys in EXPECTED_DETAIL_KEYS.items():
        template = ACHIEVEMENT_TEMPLATES[category]
        assert {field.key for field in template.fields} == expected_keys
        assert template.title_field.key == "title"
        assert "title" not in expected_keys
        assert "level" not in expected_keys


def test_templates_preserve_required_metadata_and_original_copy():
    for category, template in ACHIEVEMENT_TEMPLATES.items():
        assert template.title_copy == EXPECTED_TITLE_COPY[category]
        assert template.title_field.required is True
        assert all(field.required is True for field in template.fields)
        for field in (template.title_field, *template.fields):
            assert field.key
            assert field.label
            assert field.type in {"text", "number", "select", "textarea", "bool", "url"}
            assert isinstance(field.enum, tuple)
            assert isinstance(field.hint, str)


def test_level_is_used_only_by_the_four_defined_categories():
    level_categories = {category for category, item in ACHIEVEMENT_TEMPLATES.items() if item.level_usage}
    assert level_categories == {"award", "research", "innovation", "arts"}

    for category, template in ACHIEVEMENT_TEMPLATES.items():
        assert (template.level_field is not None) is template.level_usage
        if template.level_field:
            assert template.level_field.key == "level"
            expected = ARTS_LEVEL_OPTIONS if category == "arts" else STANDARD_LEVEL_OPTIONS
            assert template.level_field.enum == expected


def test_required_enums_and_organization_position_are_defined():
    assert field_map("paper")["paper_type"].enum == ("期刊论文", "会议论文", "工作论文", "其他")
    assert field_map("patent")["patent_type"].enum == ("发明专利", "软件著作权", "实用新型", "外观设计")
    assert field_map("innovation")["project_category"].enum == ("创新项目", "创业项目")
    assert field_map("organization")["assessment"].enum == ("优秀", "良好", "合格")
    assert field_map("organization")["position"].label == "职务"
    assert field_map("organization")["position"].type == "text"

    for category in ("paper", "award", "social"):
        for field in ACHIEVEMENT_TEMPLATES[category].fields:
            if field.type == "bool":
                assert field.enum == ("是", "否")


def test_validation_and_placeholder_metadata_is_expressed():
    paper = field_map("paper")
    assert paper["pub_year"].format == "year:1900-current"
    assert paper["pub_month"].format == "month:1-12"
    assert paper["wos_url"].format == "url"
    assert paper["citation_count"].format == "non-negative-integer"
    assert "forthcoming" in paper["pages"].format

    assert field_map("research")["project_funding"].format == "decimal-2|无"
    for category in ("research", "innovation", "organization", "social", "arts"):
        assert "进行中" in field_map(category)["end_year"].format
        assert "进行中" in field_map(category)["end_month"].format
    assert "无" in field_map("patent")["grant_year"].format
    assert "无" in field_map("patent")["grant_month"].format


@pytest.mark.parametrize(
    ("category", "details", "expected_year", "expected_date"),
    [
        ("paper", {"pub_year": 2026, "pub_month": 6}, 2026, "2026-06"),
        ("award", {"award_year": "2025", "award_month": "9"}, 2025, "2025-09"),
        ("research", {"project_year": 2024, "start_month": 3}, 2024, "2024-03"),
        ("patent", {"grant_year": 2026, "grant_month": 8, "apply_year": 2025, "apply_month": 6}, 2026, "2026-08"),
        ("innovation", {"start_year": 2023, "start_month": 2}, 2023, "2023-02"),
        ("organization", {"start_year": 2022, "start_month": 9}, 2022, "2022-09"),
        ("social", {"start_year": 2025, "start_month": 7}, 2025, "2025-07"),
        ("arts", {"start_year": 2024, "start_month": 10}, 2024, "2024-10"),
    ],
)
def test_year_and_achievement_date_derivation(category, details, expected_year, expected_date):
    assert derive_year(category, details) == expected_year
    assert derive_achievement_date(category, details) == expected_date


@pytest.mark.parametrize("grant_year", ["无", "未授权", "", None])
def test_ungranted_patent_uses_application_year_and_month(grant_year):
    details = {
        "grant_year": grant_year,
        "grant_month": "无",
        "apply_year": "2025",
        "apply_month": "06",
    }
    assert derive_year("patent", details) == 2025
    assert derive_achievement_date("patent", details) == "2025-06"


def test_derivation_returns_none_for_missing_or_invalid_date_parts():
    assert derive_year("paper", {}) is None
    assert derive_achievement_date("paper", {"pub_year": 2026}) is None
    assert derive_achievement_date("paper", {"pub_year": 2026, "pub_month": 13}) is None
    assert derive_year("paper", {"pub_year": True}) is None


def test_unknown_category_is_rejected():
    with pytest.raises(ValueError, match="Unsupported achievement category"):
        derive_year("unknown", {})
    with pytest.raises(ValueError, match="Unsupported achievement category"):
        derive_achievement_date("unknown", {})


def test_serialized_registry_matches_frontend_consumable_shape():
    serialized = serialize_templates()
    assert set(serialized) == set(EXPECTED_DETAIL_KEYS)
    assert serialized["paper"]["fields"][0]["key"] == "authors"
    assert serialized["paper"]["fields"][0]["required"] is True
    assert serialized["paper"]["fields"][0]["enum"] == []
    assert serialized["award"]["level_field"]["key"] == "level"
    assert serialized["patent"]["year_fallback_source"] == "apply_year"
