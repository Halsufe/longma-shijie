import json
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base, local_now


def _load_json_list(value: str | None) -> list:
    if not value:
        return []
    try:
        result = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []
    return result if isinstance(result, list) else []


class PartyActivity(Base):
    __tablename__ = "party_activities"
    __table_args__ = (
        Index("ix_party_activities_status_start_at", "status", "start_at"),
        Index("ix_party_activities_category_start_at", "category", "start_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    registration_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    target_roles: Mapped[str] = mapped_column(String(30), nullable=False)
    target_member_ids_json: Mapped[str] = mapped_column(
        Text, default="[]", server_default=text("'[]'"), nullable=False
    )
    max_participants: Mapped[int | None] = mapped_column(Integer, nullable=True)
    materials_json: Mapped[str] = mapped_column(
        Text, default="[]", server_default=text("'[]'"), nullable=False
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_attachments_json: Mapped[str] = mapped_column(
        Text, default="[]", server_default=text("'[]'"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default="draft", server_default=text("'draft'"), nullable=False
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=local_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=local_now, onupdate=local_now, nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    @property
    def target_member_ids(self) -> list[int]:
        return _load_json_list(self.target_member_ids_json)

    @target_member_ids.setter
    def target_member_ids(self, value: list[int]) -> None:
        self.target_member_ids_json = json.dumps(value)

    @property
    def materials(self) -> list[dict]:
        return _load_json_list(self.materials_json)

    @materials.setter
    def materials(self, value: list[dict]) -> None:
        self.materials_json = json.dumps(value, ensure_ascii=False)

    @property
    def summary_attachments(self) -> list[dict]:
        return _load_json_list(self.summary_attachments_json)

    @summary_attachments.setter
    def summary_attachments(self, value: list[dict]) -> None:
        self.summary_attachments_json = json.dumps(value, ensure_ascii=False)


class PartyActivityParticipant(Base):
    __tablename__ = "party_activity_participants"
    __table_args__ = (
        Index(
            "uq_party_participant",
            "activity_id",
            "user_id",
            unique=True,
        ),
        Index("ix_party_participant_user", "user_id", "activity_id"),
        Index(
            "ix_party_participant_attendance",
            "activity_id",
            "attendance_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("party_activities.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    registration_status: Mapped[str] = mapped_column(
        String(20),
        default="registered",
        server_default=text("'registered'"),
        nullable=False,
    )
    attendance_status: Mapped[str] = mapped_column(
        String(20), default="none", server_default=text("'none'"), nullable=False
    )
    sign_in_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sign_in_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=local_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=local_now, onupdate=local_now, nullable=False
    )


class PartyMaterial(Base):
    __tablename__ = "party_materials"
    __table_args__ = (
        Index("ix_party_materials_user", "user_id", "material_type"),
        Index("ix_party_materials_uploaded_at", "uploaded_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    material_type: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=local_now, nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class PoliticalStatusReview(Base):
    __tablename__ = "political_status_reviews"
    __table_args__ = (
        Index("ix_political_review_status_submitted", "status", "submitted_at"),
        Index("ix_political_review_user", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    from_status: Mapped[str] = mapped_column(String(30), nullable=False)
    to_status: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default=text("'pending'"), nullable=False
    )
    submitted_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=local_now, nullable=False
    )
    reviewed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)


class PoliticalLearningMaterial(Base):
    __tablename__ = "political_materials"
    __table_args__ = (
        Index("ix_political_materials_status_created", "status", "created_at"),
        Index("ix_political_materials_created_by", "created_by"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    applicable_roles_json: Mapped[str] = mapped_column(
        Text, default="[]", server_default=text("'[]'"), nullable=False
    )
    target_user_ids_json: Mapped[str] = mapped_column(
        Text, default="[]", server_default=text("'[]'"), nullable=False
    )
    attachments_json: Mapped[str] = mapped_column(
        Text, default="[]", server_default=text("'[]'"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default="draft", server_default=text("'draft'"), nullable=False
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=local_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=local_now, onupdate=local_now, nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    @property
    def applicable_roles(self) -> list[str]:
        return _load_json_list(self.applicable_roles_json)

    @applicable_roles.setter
    def applicable_roles(self, value: list[str]) -> None:
        self.applicable_roles_json = json.dumps(value, ensure_ascii=False)

    @property
    def target_user_ids(self) -> list[int]:
        return [int(item) for item in _load_json_list(self.target_user_ids_json)]

    @target_user_ids.setter
    def target_user_ids(self, value: list[int]) -> None:
        self.target_user_ids_json = json.dumps(value)

    @property
    def attachments(self) -> list[dict]:
        return _load_json_list(self.attachments_json)

    @attachments.setter
    def attachments(self, value: list[dict]) -> None:
        self.attachments_json = json.dumps(value, ensure_ascii=False)
