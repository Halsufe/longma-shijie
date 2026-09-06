import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, DateTime, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base, local_now


class ResourceType:
    EXPERIENCE = "experience"
    MATERIAL = "material"
    TOOL = "tool"
    RECRUIT = "recruit"
    COMPETITION = "competition"
    PROJECT = "project"


class ResourceStatus:
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attachments_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="approved", nullable=False, index=True)
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    like_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: local_now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: local_now(), onupdate=lambda: local_now(), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def tags(self) -> list[str]:
        if not self.tags_json:
            return []
        try:
            return json.loads(self.tags_json)
        except (json.JSONDecodeError, TypeError):
            return []

    @tags.setter
    def tags(self, tags: list[str]) -> None:
        self.tags_json = json.dumps(tags, ensure_ascii=False)

    @property
    def attachments(self) -> list[dict]:
        if not self.attachments_json:
            return []
        try:
            return json.loads(self.attachments_json)
        except (json.JSONDecodeError, TypeError):
            return []

    @attachments.setter
    def attachments(self, attachments: list[dict]) -> None:
        self.attachments_json = json.dumps(attachments, ensure_ascii=False)


class ResourceFavorite(Base):
    __tablename__ = "resource_favorites"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: local_now(), nullable=False)


class ResourceLike(Base):
    __tablename__ = "resource_likes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: local_now(), nullable=False)