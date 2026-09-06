import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, DateTime, Integer, Text, ForeignKey, Float, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base, local_now


class AchievementCategory:
    PAPER = "paper"
    AWARD = "award"
    RESEARCH = "research"
    PATENT = "patent"
    INNOVATION = "innovation"
    ORGANIZATION = "organization"
    SOCIAL = "social"
    ARTS = "arts"


class AchievementStatus:
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Achievement(Base):
    __tablename__ = "achievements"
    __table_args__ = (
        Index("ix_achievements_user_id_achievement_date", "user_id", "achievement_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    achievement_date: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    is_public: Mapped[bool] = mapped_column(default=False, nullable=False)
    member_ids_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    proofs_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details_json: Mapped[str] = mapped_column(
        Text, default="{}", server_default=text("'{}'"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: local_now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: local_now(), onupdate=lambda: local_now(), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def member_ids(self) -> list[int]:
        if not self.member_ids_json:
            return []
        try:
            return json.loads(self.member_ids_json)
        except (json.JSONDecodeError, TypeError):
            return []

    @member_ids.setter
    def member_ids(self, ids: list[int]) -> None:
        self.member_ids_json = json.dumps(ids)

    @property
    def proofs(self) -> list[dict]:
        if not self.proofs_json:
            return []
        try:
            return json.loads(self.proofs_json)
        except (json.JSONDecodeError, TypeError):
            return []

    @proofs.setter
    def proofs(self, proofs: list[dict]) -> None:
        self.proofs_json = json.dumps(proofs, ensure_ascii=False)

    @property
    def details(self) -> dict:
        if not self.details_json:
            return {}
        try:
            value = json.loads(self.details_json)
        except (json.JSONDecodeError, TypeError):
            return {}
        return value if isinstance(value, dict) else {}

    @details.setter
    def details(self, details: dict) -> None:
        self.details_json = json.dumps(details, ensure_ascii=False)
