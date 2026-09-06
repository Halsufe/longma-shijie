"""Achievement category template registry and date derivation helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


YES_NO_OPTIONS = ("是", "否")
STANDARD_LEVEL_OPTIONS = ("国家级", "省级", "校级", "院级")
ARTS_LEVEL_OPTIONS = ("校级", "省级", "国家级")

YEAR_FORMAT = "year:1900-current"
MONTH_FORMAT = "month:1-12"
YEAR_OR_ONGOING_FORMAT = "year:1900-current|进行中"
MONTH_OR_ONGOING_FORMAT = "month:1-12|进行中"
YEAR_OR_NONE_FORMAT = "year:1900-current|无"
MONTH_OR_NONE_FORMAT = "month:1-12|无"
NAME_LIST_FORMAT = "name-list:comma-separated-no-empty-items"


@dataclass(frozen=True, slots=True)
class FieldSpec:
    key: str
    label: str
    type: str
    required: bool = True
    enum: tuple[Any, ...] = ()
    format: str | None = None
    hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["enum"] = list(self.enum)
        return data


@dataclass(frozen=True, slots=True)
class AchievementTemplate:
    category: str
    category_label: str
    title_copy: str
    title_field: FieldSpec
    fields: tuple[FieldSpec, ...]
    level_usage: bool
    year_source: str
    month_source: str
    level_field: FieldSpec | None = None
    year_fallback_source: str | None = None
    month_fallback_source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "category_label": self.category_label,
            "title_copy": self.title_copy,
            "title_field": self.title_field.to_dict(),
            "fields": [field.to_dict() for field in self.fields],
            "level_usage": self.level_usage,
            "level_field": self.level_field.to_dict() if self.level_field else None,
            "year_source": self.year_source,
            "year_fallback_source": self.year_fallback_source,
            "month_source": self.month_source,
            "month_fallback_source": self.month_fallback_source,
        }


def _field(
    key: str,
    label: str,
    field_type: str = "text",
    *,
    enum: tuple[Any, ...] = (),
    format: str | None = None,
    hint: str = "",
) -> FieldSpec:
    return FieldSpec(
        key=key,
        label=label,
        type=field_type,
        required=True,
        enum=enum,
        format=format,
        hint=hint,
    )


def _level_field(label: str, enum: tuple[str, ...] = STANDARD_LEVEL_OPTIONS) -> FieldSpec:
    return _field("level", label, "select", enum=enum, hint="请选择级别")


ACHIEVEMENT_TEMPLATES: dict[str, AchievementTemplate] = {
    "paper": AchievementTemplate(
        category="paper",
        category_label="学术论文",
        title_copy="以下是您的学术论文，您可以修改和新增。所有条目必填",
        title_field=_field("title", "标题", hint="论文题目"),
        fields=(
            _field("authors", "作者", format=NAME_LIST_FORMAT, hint="全部作者中文名，逗号分隔；通讯作者标注“（通讯）”"),
            _field("journal", "期刊", hint="期刊全称；期刊名首词为 the 时省略该词"),
            _field("sci_indexed", "SCI检索", "bool", enum=YES_NO_OPTIONS, hint="请选择是或否"),
            _field("ssci_indexed", "SSCI检索", "bool", enum=YES_NO_OPTIONS, hint="请选择是或否"),
            _field("cssci_indexed", "CSSCI检索", "bool", enum=YES_NO_OPTIONS, hint="请选择是或否"),
            _field(
                "is_top_journal",
                "是否顶刊",
                "bool",
                enum=YES_NO_OPTIONS,
                hint="AUTD24、FT50、ABS4及以上、Nature、Science、Cell系列可认定为顶刊",
            ),
            _field(
                "paper_type",
                "论文类型",
                "select",
                enum=("期刊论文", "会议论文", "工作论文", "其他"),
                hint="请选择论文类型",
            ),
            _field("pub_year", "发表年份", "number", format=YEAR_FORMAT, hint="4位数字，如2026"),
            _field("pub_month", "发表月份", "number", format=MONTH_FORMAT, hint="1-12"),
            _field("wos_url", "WoS链接", "url", format="url", hint="合法URL，如https://..."),
            _field("volume", "卷号", hint="允许包含字母"),
            _field("issue", "期号"),
            _field("citation_count", "引用次数", "number", format="non-negative-integer", hint="非负整数"),
            _field("research_direction", "研究方向"),
            _field("pages", "页码", format="page-range|forthcoming", hint="如20-30；没有页码填forthcoming"),
            _field("keywords", "关键词", format="text-list:comma-separated-no-empty-items", hint="逗号分隔"),
            _field("doi", "DOI", hint="如10.xxxx/xxxx"),
            _field("abstract", "摘要", "textarea"),
        ),
        level_usage=False,
        year_source="pub_year",
        month_source="pub_month",
    ),
    "award": AchievementTemplate(
        category="award",
        category_label="竞赛获奖",
        title_copy="以下是您的竞赛获奖记录，您可以修改和新增。所有条目必填",
        title_field=_field("title", "竞赛名称", hint="完整的竞赛名称"),
        fields=(
            _field("award_grade", "获奖等级", hint="未获奖填“无”"),
            _field("organizer", "主办单位", hint="主办单位全称"),
            _field("award_year", "获奖年份", "number", format=YEAR_FORMAT, hint="4位数字，如2026"),
            _field("award_month", "获奖月份", "number", format=MONTH_FORMAT, hint="1-12"),
            _field("teacher_names", "指导教师", format=NAME_LIST_FORMAT, hint="多人姓名以逗号分隔"),
            _field("is_team", "是否团队", "bool", enum=YES_NO_OPTIONS, hint="请选择是或否"),
            _field("is_leader", "是否责任人", "bool", enum=YES_NO_OPTIONS, hint="请选择是或否"),
            _field("member_names", "成员名单", format=NAME_LIST_FORMAT, hint="逗号分隔；非团队时填本人姓名"),
            _field("description", "描述", "textarea"),
        ),
        level_usage=True,
        level_field=_level_field("赛事级别"),
        year_source="award_year",
        month_source="award_month",
    ),
    "research": AchievementTemplate(
        category="research",
        category_label="项目课题",
        title_copy="以下是您的项目课题记录，您可以修改和新增。所有条目必填",
        title_field=_field("title", "项目名称", hint="完整的项目名称"),
        fields=(
            _field("project_unit", "项目所属单位"),
            _field("project_field", "项目领域"),
            _field("project_funding", "项目经费", format="decimal-2|无", hint="数字保留两位小数；无经费填“无”"),
            _field("leader_name", "主持人", hint="姓名"),
            _field("participant_names", "参与人", format=NAME_LIST_FORMAT, hint="多人姓名以逗号分隔"),
            _field("project_year", "立项年份", "number", format=YEAR_FORMAT, hint="4位数字"),
            _field("start_year", "开始年份", "number", format=YEAR_FORMAT, hint="4位数字"),
            _field("start_month", "开始月份", "number", format=MONTH_FORMAT, hint="1-12"),
            _field("end_year", "结束年份", format=YEAR_OR_ONGOING_FORMAT, hint="4位数字；进行中填“进行中”"),
            _field("end_month", "结束月份", format=MONTH_OR_ONGOING_FORMAT, hint="1-12；进行中填“进行中”"),
            _field("approval_no", "批准文号"),
        ),
        level_usage=True,
        level_field=_level_field("项目级别"),
        year_source="project_year",
        month_source="start_month",
    ),
    "patent": AchievementTemplate(
        category="patent",
        category_label="软著专利",
        title_copy="以下是您的专利/软著记录，您可以修改和新增。所有条目必填",
        title_field=_field("title", "专利/软著名", hint="完整的专利或软著名称"),
        fields=(
            _field(
                "patent_type",
                "类型",
                "select",
                enum=("发明专利", "软件著作权", "实用新型", "外观设计"),
                hint="请选择类型",
            ),
            _field("participant_names", "参与人", format=NAME_LIST_FORMAT, hint="多人姓名以逗号分隔"),
            _field("field", "所属领域"),
            _field("apply_year", "申请年份", "number", format=YEAR_FORMAT, hint="4位数字"),
            _field("apply_month", "申请月份", "number", format=MONTH_FORMAT, hint="1-12"),
            _field("grant_year", "授权年份", format=YEAR_OR_NONE_FORMAT, hint="4位数字；未授权填“无”"),
            _field("grant_month", "授权月份", format=MONTH_OR_NONE_FORMAT, hint="1-12；未授权填“无”"),
            _field("application_no", "申请号"),
            _field("grant_no", "授权号", hint="未授权填“无”"),
            _field("abstract", "摘要", "textarea"),
        ),
        level_usage=False,
        year_source="grant_year",
        year_fallback_source="apply_year",
        month_source="grant_month",
        month_fallback_source="apply_month",
    ),
    "innovation": AchievementTemplate(
        category="innovation",
        category_label="创新创业",
        title_copy="以下是您的创新创业项目列表，您可以查看、修改或新增。所有条目必填",
        title_field=_field("title", "项目名称", hint="完整的项目名称"),
        fields=(
            _field("project_category", "项目类别", "select", enum=("创新项目", "创业项目"), hint="请选择项目类别"),
            _field("leader_name", "主持人", hint="姓名"),
            _field("member_names", "团队成员", format=NAME_LIST_FORMAT, hint="多人姓名以逗号分隔"),
            _field("teacher_names", "指导教师", format=NAME_LIST_FORMAT, hint="多人姓名以逗号分隔"),
            _field("start_year", "开始年份", "number", format=YEAR_FORMAT, hint="4位数字"),
            _field("start_month", "开始月份", "number", format=MONTH_FORMAT, hint="1-12"),
            _field("end_year", "结束年份", format=YEAR_OR_ONGOING_FORMAT, hint="4位数字；进行中填“进行中”"),
            _field("end_month", "结束月份", format=MONTH_OR_ONGOING_FORMAT, hint="1-12；进行中填“进行中”"),
            _field("summary", "项目简介", "textarea"),
        ),
        level_usage=True,
        level_field=_level_field("结项级别"),
        year_source="start_year",
        month_source="start_month",
    ),
    "organization": AchievementTemplate(
        category="organization",
        category_label="组织管理",
        title_copy="以下是您的组织或部门任职经历信息，您可以修改和新增。所有条目必填",
        title_field=_field("title", "任职部门", hint="所在部门或机构"),
        fields=(
            _field("position", "职务", hint="填写所任职务，如部长、会长"),
            _field("assessment", "考核评定", "select", enum=("优秀", "良好", "合格"), hint="请选择组织考核结果"),
            _field("honor_title", "荣誉称号", hint="未获得填“无”"),
            _field("start_year", "开始年份", "number", format=YEAR_FORMAT, hint="4位数字"),
            _field("start_month", "开始月份", "number", format=MONTH_FORMAT, hint="1-12"),
            _field("end_year", "结束年份", format=YEAR_OR_ONGOING_FORMAT, hint="4位数字；在任期间填“进行中”"),
            _field("end_month", "结束月份", format=MONTH_OR_ONGOING_FORMAT, hint="1-12；在任期间填“进行中”"),
        ),
        level_usage=False,
        year_source="start_year",
        month_source="start_month",
    ),
    "social": AchievementTemplate(
        category="social",
        category_label="社会实践",
        title_copy="以下是您的社会实践信息，您可以修改和新增。所有条目必填",
        title_field=_field("title", "活动名称"),
        fields=(
            _field("practice_unit", "实践单位"),
            _field("is_team", "是否团队", "bool", enum=YES_NO_OPTIONS, hint="请选择是或否"),
            _field("member_names", "成员", format=NAME_LIST_FORMAT, hint="逗号分隔，负责人标星"),
            _field("is_leader", "是否负责人", "bool", enum=YES_NO_OPTIONS, hint="请选择是或否"),
            _field("start_year", "开始年份", "number", format=YEAR_FORMAT, hint="4位数字"),
            _field("start_month", "开始月份", "number", format=MONTH_FORMAT, hint="1-12"),
            _field("end_year", "结束年份", format=YEAR_OR_ONGOING_FORMAT, hint="4位数字；持续活动填“进行中”"),
            _field("end_month", "结束月份", format=MONTH_OR_ONGOING_FORMAT, hint="1-12；持续活动填“进行中”"),
            _field("process_description", "实践过程概述", "textarea"),
        ),
        level_usage=False,
        year_source="start_year",
        month_source="start_month",
    ),
    "arts": AchievementTemplate(
        category="arts",
        category_label="文体活动",
        title_copy="以下是您的文体活动信息，您可以修改和新增。所有条目必填",
        title_field=_field("title", "活动名称"),
        fields=(
            _field("organizer", "主办单位"),
            _field("start_year", "开始年份", "number", format=YEAR_FORMAT, hint="4位数字"),
            _field("start_month", "开始月份", "number", format=MONTH_FORMAT, hint="1-12"),
            _field("end_year", "结束年份", format=YEAR_OR_ONGOING_FORMAT, hint="4位数字；持续活动填“进行中”"),
            _field("end_month", "结束月份", format=MONTH_OR_ONGOING_FORMAT, hint="1-12；持续活动填“进行中”"),
            _field("summary", "活动概述", "textarea"),
        ),
        level_usage=True,
        level_field=_level_field("活动级别", ARTS_LEVEL_OPTIONS),
        year_source="start_year",
        month_source="start_month",
    ),
}

TEMPLATES = ACHIEVEMENT_TEMPLATES


def get_template(category: str) -> AchievementTemplate:
    try:
        return ACHIEVEMENT_TEMPLATES[category]
    except KeyError as exc:
        raise ValueError(f"Unsupported achievement category: {category}") from exc


def serialize_templates() -> dict[str, dict[str, Any]]:
    return {category: template.to_dict() for category, template in ACHIEVEMENT_TEMPLATES.items()}


def _coerce_year(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    text = str(value).strip() if value is not None else ""
    if len(text) != 4 or not text.isdigit():
        return None
    year = int(text)
    return year if 1900 <= year <= 9999 else None


def _coerce_month(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    text = str(value).strip() if value is not None else ""
    if not text.isdigit():
        return None
    month = int(text)
    return month if 1 <= month <= 12 else None


def _uses_fallback_year(template: AchievementTemplate, details: Mapping[str, Any]) -> bool:
    return bool(
        template.year_fallback_source
        and _coerce_year(details.get(template.year_source)) is None
    )


def derive_year(category: str, details: Mapping[str, Any] | None) -> int | None:
    """Derive the normalized achievement year for a category."""
    template = get_template(category)
    values = details or {}
    year = _coerce_year(values.get(template.year_source))
    if year is None and template.year_fallback_source:
        year = _coerce_year(values.get(template.year_fallback_source))
    return year


def derive_achievement_date(category: str, details: Mapping[str, Any] | None) -> str | None:
    """Derive a normalized ``YYYY-MM`` date from category-specific fields."""
    template = get_template(category)
    values = details or {}
    uses_fallback = _uses_fallback_year(template, values)
    year = derive_year(category, values)

    month_source = template.month_source
    if uses_fallback and template.month_fallback_source:
        month_source = template.month_fallback_source
    month = _coerce_month(values.get(month_source))

    if year is None or month is None:
        return None
    return f"{year:04d}-{month:02d}"
