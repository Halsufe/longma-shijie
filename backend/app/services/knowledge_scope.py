from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class KnowledgeScope(str, Enum):
    PERSONAL = "personal"
    CLASS = "class"
    NONE = "none"


class InvalidKnowledgeScope(ValueError):
    """Raised when a client tries to use an unsupported retrieval scope."""


@dataclass(frozen=True)
class AuthorizedRetrievalContext:
    user_id: int
    scope: KnowledgeScope
    class_id: int | None
    index_key: str | None
    web_search_enabled: bool
    cache_partition: str


class KnowledgeScopeGuard:
    allowed = frozenset(item.value for item in KnowledgeScope)

    @classmethod
    def parse(cls, value: str | None) -> KnowledgeScope:
        normalized = (value or KnowledgeScope.PERSONAL.value).strip().lower()
        if normalized not in cls.allowed:
            raise InvalidKnowledgeScope(
                "knowledge_scope must be one of personal, class, or none"
            )
        return KnowledgeScope(normalized)

    @staticmethod
    def _class_id(user: Any) -> int | None:
        import zlib

        for source in (getattr(user, "profile", {}) or {}, getattr(user, "party", {}) or {}):
            if not isinstance(source, dict):
                continue
            value = (
                source.get("class_id")
                or source.get("classId")
                or source.get("class")
                or source.get("class_name")
            )
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.isdigit():
                return int(value)
            if isinstance(value, str) and value.strip():
                return zlib.crc32(value.strip().encode("utf-8")) & 0x7FFFFFFF
        return None

    @classmethod
    def authorize(
        cls,
        db: "Session",
        user: Any,
        scope: str | None,
        *,
        web_search_enabled: bool = True,
    ) -> AuthorizedRetrievalContext:
        parsed = cls.parse(scope)
        class_id = cls._class_id(user)
        if parsed is KnowledgeScope.CLASS and class_id is None:
            # Existing deployments have a single global class administrator
            # without a membership profile. Keep that management path valid;
            # regular users still need an explicit class membership.
            if getattr(user, "is_admin", False) or getattr(user, "role", None) == "admin":
                class_id = 0
            else:
                raise PermissionError("当前用户不属于可用班级知识库")
        index_key = None if parsed is KnowledgeScope.NONE else f"{parsed.value}:{user.id if parsed is KnowledgeScope.PERSONAL else class_id}"
        return AuthorizedRetrievalContext(
            user_id=int(user.id),
            scope=parsed,
            class_id=class_id if parsed is KnowledgeScope.CLASS else None,
            index_key=index_key,
            web_search_enabled=bool(web_search_enabled),
            cache_partition=f"chat:{user.id}:{parsed.value}:{class_id if parsed is KnowledgeScope.CLASS else '-'}",
        )
