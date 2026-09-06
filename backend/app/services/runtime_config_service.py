import json
from typing import Any

from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.runtime_config import RuntimeConfig


class RuntimeConfigService:
    """Persist and apply the small, explicitly supported runtime-config surface."""

    SPECS: dict[str, tuple[str, type, Any]] = {
        "class_name": ("CLASS_NAME", str, "大数据管理与应用25级"),
        "default_quota_mb": ("DEFAULT_QUOTA_MB", int, 500),
        "login_max_attempts": ("LOGIN_MAX_ATTEMPTS", int, 10),
        "login_window_minutes": ("LOGIN_WINDOW_MINUTES", int, 5),
        "ai_model": ("AI_MODEL", str, ""),
        "ai_base_url": ("AI_BASE_URL", str, ""),
        "assignment_reminder_hours": ("ASSIGNMENT_REMINDER_HOURS", list, [24, 2]),
    }

    @classmethod
    def _validate(cls, key: str, value: Any) -> Any:
        if key not in cls.SPECS:
            raise ValueError(f"不支持的配置项: {key}")
        _, expected, _ = cls.SPECS[key]
        if expected is int and (not isinstance(value, int) or isinstance(value, bool) or value <= 0):
            raise ValueError(f"配置项 {key} 必须为正整数")
        if expected is str and (not isinstance(value, str) or len(value) > 500):
            raise ValueError(f"配置项 {key} 必须为不超过500字符的字符串")
        if expected is list:
            if not isinstance(value, list) or not value or len(value) > 20:
                raise ValueError(f"配置项 {key} 必须为非空整数数组")
            if any(not isinstance(item, int) or isinstance(item, bool) or item <= 0 for item in value):
                raise ValueError(f"配置项 {key} 必须为正整数数组")
            value = sorted(set(value), reverse=True)
        return value

    @classmethod
    def load(cls, db: Session) -> dict[str, Any]:
        values = cls.current()
        for row in db.query(RuntimeConfig).all():
            if row.key not in cls.SPECS:
                continue
            try:
                values[row.key] = cls._validate(row.key, json.loads(row.value_json))
            except (ValueError, TypeError, json.JSONDecodeError):
                continue
        cls._apply(values)
        return values

    @classmethod
    def current(cls) -> dict[str, Any]:
        return {key: getattr(settings, attr) for key, (attr, _, __) in cls.SPECS.items()}

    @classmethod
    def update(cls, db: Session, changes: dict[str, Any], user_id: int) -> dict[str, Any]:
        clean = {key: cls._validate(key, value) for key, value in changes.items()}
        try:
            for key, value in clean.items():
                row = db.get(RuntimeConfig, key)
                if row is None:
                    row = RuntimeConfig(key=key, value_json="null", updated_by=user_id)
                    db.add(row)
                row.value_json = json.dumps(value, ensure_ascii=False)
                row.updated_by = user_id
            db.commit()
        except Exception:
            db.rollback()
            raise
        cls._apply(clean)
        if {"ai_model", "ai_base_url"} & clean.keys():
            # The adapter is a process singleton; invalidate it so changes in
            # the admin configuration take effect on the next request.
            from backend.app.ai.base import reset_adapter
            reset_adapter()
        return cls.current()

    @classmethod
    def _apply(cls, values: dict[str, Any]) -> None:
        for key, value in values.items():
            spec = cls.SPECS.get(key)
            if spec:
                setattr(settings, spec[0], value)
