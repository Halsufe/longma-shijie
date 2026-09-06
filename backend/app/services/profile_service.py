import re
from typing import Any

from backend.app.models.user import User

PROFILE_LIMITS = {
    "interests": (20, 50),
    "development_plan": (2000, None),
    "grade": (30, None),
}
PROFILE_KEYS = {
    "major", "research", "field", "skills", "bio", "interests", "development_plan", "grade",
    "current_job", "title", "department", "directions", "phone", "email", "course_grades",
}

_PHONE_RE = re.compile(r"^(?:\+?86[- ]?)?1[3-9]\d{9}$")
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def normalize_profile(profile: dict[str, Any] | None) -> dict[str, Any]:
    """Keep legacy profile keys while validating the common profile extension."""
    if profile is None:
        return {}
    result: dict[str, Any] = {}
    for key, value in profile.items():
        if key not in PROFILE_KEYS:
            continue
        if value is None:
            continue
        if key == "course_grades":
            if not isinstance(value, list):
                raise ValueError("course_grades 必须是列表")
            grades = []
            for item in value:
                if not isinstance(item, dict):
                    raise ValueError("课程成绩项格式错误")
                course_name = str(item.get("course_name") or "").strip()
                score = str(item.get("score") or "").strip()
                remark = str(item.get("remark") or "").strip()
                if not course_name or not score:
                    raise ValueError("课程名称和成绩不能为空")
                grades.append({"course_name": course_name, "score": score, "remark": remark})
            value = grades
        elif key in {"interests", "skills", "research", "directions"}:
            if isinstance(value, str):
                value = [item.strip() for item in value.replace("，", ",").replace("/", ",").split(",") if item.strip()]
            max_items = PROFILE_LIMITS.get(key, (None, 20))[1]
            if not isinstance(value, list) or (max_items is not None and len(value) > max_items):
                raise ValueError(f"{key} 最多支持 {max_items} 项")
            value = [str(item).strip() for item in value if str(item).strip()]
            item_limit = PROFILE_LIMITS.get(key, (None, 50))[1] or 50
            if any(len(item) > item_limit for item in value):
                raise ValueError(f"{key} 单项不能超过 {item_limit} 个字符")
        else:
            value = str(value).strip()
            if key == "phone" and value and not _PHONE_RE.fullmatch(value.replace(" ", "")):
                raise ValueError("手机号格式不正确")
            if key == "email" and value and not _EMAIL_RE.fullmatch(value):
                raise ValueError("邮箱格式不正确")
            max_len = PROFILE_LIMITS.get(key, (None, None))[0]
            if max_len and len(value) > max_len:
                raise ValueError(f"{key} 超出长度限制")
        result[key] = value
    return result


def validate_mentor_selection_profile(profile: dict[str, Any]) -> None:
    """Validate the fields required only when formally submitting preferences."""
    normalized = normalize_profile(profile)
    if not str(normalized.get("bio") or "").strip():
        raise ValueError("个人简介不能为空")
    if len(normalized.get("course_grades") or []) < 3:
        raise ValueError("至少填写 3 门课程成绩")


def update_profile(user: User, profile: dict[str, Any] | None) -> None:
    user.profile = normalize_profile(profile)
