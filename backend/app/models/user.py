import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, String, Text, Integer, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column

import enum

from backend.app.core.database import Base, local_now


class UserRole(str, enum.Enum):
    STUDENT = "student"
    ALUMNI = "alumni"
    TEACHER = "teacher"
    ADMIN = "admin"


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    PENDING_CHANGE = "pending_change"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default=UserRole.STUDENT.value, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default=UserStatus.PENDING_CHANGE.value, nullable=False)
    graduation_year: Mapped[Optional[int]] = mapped_column(nullable=True)
    profile_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    party_json: Mapped[str] = mapped_column(Text, default="{}", server_default=text("'{}'"), nullable=False)
    political_status: Mapped[str] = mapped_column(
        String(30), default="群众", server_default=text("'群众'"), nullable=False
    )
    political_status_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: local_now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: local_now(),
        onupdate=lambda: local_now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def profile(self) -> dict:
        if not self.profile_json:
            return {}
        try:
            return json.loads(self.profile_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    @profile.setter
    def profile(self, data: dict) -> None:
        self.profile_json = json.dumps(data, ensure_ascii=False)

    @property
    def party(self) -> dict:
        if not self.party_json:
            return {}
        try:
            value = json.loads(self.party_json)
        except (json.JSONDecodeError, TypeError):
            return {}
        return value if isinstance(value, dict) else {}

    @party.setter
    def party(self, data: dict) -> None:
        self.party_json = json.dumps(data, ensure_ascii=False)

    @property
    def is_student(self) -> bool:
        return self.role == UserRole.STUDENT.value

    @property
    def is_alumni(self) -> bool:
        return self.role == UserRole.ALUMNI.value

    @property
    def is_teacher(self) -> bool:
        return self.role == UserRole.TEACHER.value

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN.value


class AlumniConversionRequest(Base):
    __tablename__ = "alumni_conversion_requests"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    graduation_year: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: local_now(), nullable=False)
