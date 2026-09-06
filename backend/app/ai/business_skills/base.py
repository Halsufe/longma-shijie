"""Shared contract for business Skill executors."""

from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.orm import Session

from backend.app.models.user import User


class BusinessSkillPermissionError(PermissionError):
    """Raised when the current user cannot perform a business Skill request."""


class BusinessSkillExecutor(ABC):
    """Base class implemented by every business Skill execution module."""

    skill_name: str

    @abstractmethod
    async def execute(self, user_input: str, user: User, db: Session) -> dict[str, Any]:
        """Return a structured, JSON-serializable business result."""
        raise NotImplementedError

    @staticmethod
    def normalize_input(user_input: str) -> str:
        return " ".join(user_input.strip().split())

