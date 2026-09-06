"""Validation and normalization for achievement template payloads."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from backend.app.services.achievement_templates import (
    MONTH_FORMAT,
    MONTH_OR_NONE_FORMAT,
    MONTH_OR_ONGOING_FORMAT,
    NAME_LIST_FORMAT,
    YEAR_FORMAT,
    YEAR_OR_NONE_FORMAT,
    YEAR_OR_ONGOING_FORMAT,
    derive_achievement_date,
    get_template,
)


DETAIL_METADATA_FIELDS = {"source_type", "source_id"}


class AchievementValidationError(ValueError):
    def __init__(self, errors: dict[str, str]):
        self.errors = errors
        super().__init__("; ".join(f"{field}: {message}" for field, message in errors.items()))


def validate_category(category: str) -> None:
    try:
        get_template(category)
    except ValueError as exc:
        raise AchievementValidationError({"category": "不支持的成果类别"}) from exc


def validate_level(category: str, level: Any) -> str | None:
    validate_category(category)
    template = get_template(category)
    field_name = "level"

    if not template.level_usage:
        if level is None or (isinstance(level, str) and not level.strip()):
            return None
        raise AchievementValidationError({field_name: "该成果类别不使用级别字段"})

    if not isinstance(level, str) or not level.strip():
        raise AchievementValidationError({field_name: "必填字段不能为空"})

    normalized = level.strip()
    allowed = template.level_field.enum if template.level_field else ()
    if allowed and normalized not in allowed:
        raise AchievementValidationError({field_name: f"必须是以下值之一：{', '.join(allowed)}"})
    return normalized


def validate_details(category: str, details: Mapping[str, Any] | None) -> dict[str, Any]:
    validate_category(category)
    if not isinstance(details, Mapping):
        raise AchievementValidationError({"details": "必须是对象"})

    template = get_template(category)
    field_specs = {field.key: field for field in template.fields}
    errors: dict[str, str] = {}
    normalized: dict[str, Any] = {}

    for key in details:
        if (
            not isinstance(key, str)
            or key not in field_specs
            and key not in DETAIL_METADATA_FIELDS
        ):
            errors[f"details.{key}"] = "该字段不属于当前成果模板"

    for key, field in field_specs.items():
        value = details.get(key)
        field_name = f"details.{key}"
        if field.required and _is_blank(value):
            errors[field_name] = "必填字段不能为空"
            continue

        try:
            normalized[key] = _normalize_field_value(field.type, field.format, field.enum, value)
        except ValueError as exc:
            errors[field_name] = str(exc)

    if "source_type" in details:
        source_type = details.get("source_type")
        if not isinstance(source_type, str) or not source_type.strip():
            errors["details.source_type"] = "必须是非空文本"
        else:
            normalized["source_type"] = source_type.strip()
    if "source_id" in details:
        source_id = details.get("source_id")
        if (
            not isinstance(source_id, (str, int))
            or isinstance(source_id, bool)
            or not str(source_id).strip()
        ):
            errors["details.source_id"] = "必须是非空文本或整数"
        else:
            normalized["source_id"] = (
                source_id if isinstance(source_id, int) else source_id.strip()
            )

    _validate_placeholder_pairs(category, normalized, errors)
    if errors:
        raise AchievementValidationError(errors)
    return normalized


def derive_validated_date(category: str, details: Mapping[str, Any]) -> str:
    achievement_date = derive_achievement_date(category, details)
    if achievement_date is None:
        raise AchievementValidationError({"achievement_date": "无法从模板年月字段派生成果日期"})
    return achievement_date


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _normalize_field_value(
    field_type: str,
    field_format: str | None,
    enum_values: tuple[Any, ...],
    value: Any,
) -> Any:
    if field_type == "bool":
        if isinstance(value, bool):
            return value
        if value == "是":
            return True
        if value == "否":
            return False
        raise ValueError("必须是布尔值或“是/否”")

    if field_format == YEAR_FORMAT:
        return _normalize_year(value)
    if field_format == MONTH_FORMAT:
        return _normalize_month(value)
    if field_format == YEAR_OR_ONGOING_FORMAT:
        return "进行中" if value == "进行中" else _normalize_year(value)
    if field_format == MONTH_OR_ONGOING_FORMAT:
        return "进行中" if value == "进行中" else _normalize_month(value)
    if field_format == YEAR_OR_NONE_FORMAT:
        return "无" if value == "无" else _normalize_year(value)
    if field_format == MONTH_OR_NONE_FORMAT:
        return "无" if value == "无" else _normalize_month(value)
    if field_format == "non-negative-integer":
        return _normalize_non_negative_integer(value)
    if field_format == "decimal-2|无":
        return _normalize_decimal(value)
    if field_format == "url":
        return _normalize_url(value)
    if field_format == "page-range|forthcoming":
        return _normalize_page_range(value)
    if field_format in {NAME_LIST_FORMAT, "text-list:comma-separated-no-empty-items"}:
        return _normalize_list_text(value)

    if not isinstance(value, str):
        raise ValueError("必须是文本")
    normalized = value.strip()
    if enum_values and normalized not in enum_values:
        raise ValueError(f"必须是以下值之一：{', '.join(str(item) for item in enum_values)}")
    return normalized


def _normalize_year(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("必须是4位年份")
    text = str(value).strip()
    if not re.fullmatch(r"\d{4}", text):
        raise ValueError("必须是4位年份")
    year = int(text)
    if not 1900 <= year <= datetime.now().year:
        raise ValueError(f"年份必须在1900至{datetime.now().year}之间")
    return year


def _normalize_month(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("月份必须在1至12之间")
    text = str(value).strip()
    if not text.isdigit() or not 1 <= int(text) <= 12:
        raise ValueError("月份必须在1至12之间")
    return int(text)


def _normalize_non_negative_integer(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("必须是非负整数")
    text = str(value).strip()
    if not text.isdigit():
        raise ValueError("必须是非负整数")
    return int(text)


def _normalize_decimal(value: Any) -> str:
    if value == "无":
        return value
    text = str(value).strip()
    if not re.fullmatch(r"\d+\.\d{2}", text):
        raise ValueError("必须是保留两位小数的非负数字，或“无”")
    return text


def _normalize_url(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("必须是合法的HTTP或HTTPS URL")
    text = value.strip()
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("必须是合法的HTTP或HTTPS URL")
    return text


def _normalize_page_range(value: Any) -> str:
    if value == "forthcoming":
        return value
    if not isinstance(value, str):
        raise ValueError("必须是页码范围，如20-30，或forthcoming")
    match = re.fullmatch(r"\s*(\d+)\s*-\s*(\d+)\s*", value)
    if not match or int(match.group(1)) > int(match.group(2)):
        raise ValueError("必须是页码范围，如20-30，或forthcoming")
    return f"{match.group(1)}-{match.group(2)}"


def _normalize_list_text(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("必须是逗号分隔且不含空项的文本")
    text = value.strip()
    items = re.split(r"[,，]", text)
    if not items or any(not item.strip() for item in items):
        raise ValueError("必须是逗号分隔且不含空项的文本")
    return text


def _validate_placeholder_pairs(
    category: str,
    details: Mapping[str, Any],
    errors: dict[str, str],
) -> None:
    if category == "patent":
        _require_matching_placeholder(details, errors, "grant_year", "grant_month", "无")
    if category in {"research", "innovation", "organization", "social", "arts"}:
        _require_matching_placeholder(details, errors, "end_year", "end_month", "进行中")


def _require_matching_placeholder(
    details: Mapping[str, Any],
    errors: dict[str, str],
    year_key: str,
    month_key: str,
    placeholder: str,
) -> None:
    year_is_placeholder = details.get(year_key) == placeholder
    month_is_placeholder = details.get(month_key) == placeholder
    if year_is_placeholder != month_is_placeholder:
        errors[f"details.{month_key}"] = f"必须与{year_key}同时填写“{placeholder}”或同时填写年月"


class AchievementService:
    validate_category = staticmethod(validate_category)
    validate_level = staticmethod(validate_level)
    validate_details = staticmethod(validate_details)
    derive_validated_date = staticmethod(derive_validated_date)
