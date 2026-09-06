from __future__ import annotations

from typing import Any

from backend.app.services.knowledge_scope import KnowledgeScopeGuard


def managed_class_ids(admin: Any) -> set[int] | None:
    """Return an administrator's class scope; None preserves legacy global admins."""
    values: list[Any] = []
    for source in (getattr(admin, "profile", {}) or {}, getattr(admin, "party", {}) or {}):
        if not isinstance(source, dict):
            continue
        for key in ("managed_class_ids", "managed_classes", "class_ids"):
            value = source.get(key)
            if isinstance(value, (list, tuple, set)):
                values.extend(value)
            elif value is not None:
                values.append(value)
    normalized: set[int] = set()
    for value in values:
        if isinstance(value, int):
            normalized.add(value)
        elif isinstance(value, str) and value.strip().isdigit():
            normalized.add(int(value.strip()))
    return normalized or None


def user_class_id(user: Any) -> int | None:
    try:
        return KnowledgeScopeGuard._class_id(user)
    except (AttributeError, TypeError):
        return None


def can_manage_user(admin: Any, target: Any) -> bool:
    allowed = managed_class_ids(admin)
    return allowed is None or user_class_id(target) in allowed
