"""Academic mentor selection domain models.

The domain is deliberately kept separate from the legacy communication
application tables.  JSON/text is used only for snapshots that are not
queried as relational data; all entities that participate in matching have
their own rows and constraints.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base, local_now


class BatchStatus:
    DRAFT = "draft"
    STUDENT_APPLY = "student_apply"
    MENTOR_SELECT = "mentor_select"
    MAIN_PENDING = "main_pending"
    MAIN_PUBLISHED = "main_published"
    SUPPLEMENT_STUDENT_APPLY = "supplement_student_apply"
    SUPPLEMENT_MENTOR_SELECT = "supplement_mentor_select"
    SUPPLEMENT_PENDING = "supplement_pending"
    SUPPLEMENT_BLOCKED = "supplement_blocked"
    SUPPLEMENT_PUBLISHED = "supplement_published"
    COMPLETED = "completed"
    REOPENED = "reopened"


class SelectionRound:
    MAIN = "main"
    SUPPLEMENT = "supplement"


class PreferenceStatus:
    DRAFT = "draft"
    SUBMITTED = "submitted"
    WITHDRAWN = "withdrawn"
    LOCKED = "locked"


class DecisionStatus:
    DRAFT = "draft"
    SUBMITTED = "submitted"


class MentorSelectionBatch(Base):
    __tablename__ = "mentor_selection_batches"
    __table_args__ = (Index("ix_mentor_selection_batches_status", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    academic_year: Mapped[str] = mapped_column(String(20), nullable=False)
    term: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default=BatchStatus.DRAFT, nullable=False)
    active_key: Mapped[Optional[str]] = mapped_column(String(80), unique=True, nullable=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    student_apply_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    student_apply_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    mentor_select_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    mentor_select_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    main_publish_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    supplement_student_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    supplement_student_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    supplement_mentor_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    supplement_mentor_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    supplement_publish_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: local_now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: local_now(), onupdate=lambda: local_now(), nullable=False
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class MentorSelectionBatchStudent(Base):
    __tablename__ = "mentor_selection_batch_students"
    __table_args__ = (
        UniqueConstraint("batch_id", "student_id", name="uq_ms_batch_student"),
        Index("ix_ms_batch_students_batch_status", "batch_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("mentor_selection_batches.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    student_no_snapshot: Mapped[str] = mapped_column(String(50), nullable=False)
    name_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    class_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="eligible", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: local_now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: local_now(), onupdate=lambda: local_now(), nullable=False
    )


class MentorSelectionBatchMentor(Base):
    __tablename__ = "mentor_selection_batch_mentors"
    __table_args__ = (
        UniqueConstraint("batch_id", "teacher_id", name="uq_ms_batch_mentor"),
        Index("ix_ms_batch_mentors_batch_status", "batch_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("mentor_selection_batches.id", ondelete="CASCADE"), nullable=False)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    quota: Mapped[int] = mapped_column(Integer, default=4, server_default=text("4"), nullable=False)
    main_matched_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"), nullable=False)
    supplement_matched_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: local_now(), nullable=False)


class MentorPreferenceSubmission(Base):
    __tablename__ = "mentor_preference_submissions"
    __table_args__ = (
        UniqueConstraint("batch_id", "student_id", "round", "version", name="uq_ms_preference_version"),
        Index("ix_ms_preferences_lookup", "batch_id", "student_id", "round", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("mentor_selection_batches.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    round: Mapped[str] = mapped_column(String(20), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    personal_statement: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=PreferenceStatus.DRAFT, nullable=False)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    withdrawn_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: local_now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: local_now(), onupdate=lambda: local_now(), nullable=False
    )


class MentorPreferenceItem(Base):
    __tablename__ = "mentor_preference_items"
    __table_args__ = (
        UniqueConstraint("preference_id", "teacher_id", name="uq_ms_preference_teacher"),
        UniqueConstraint("preference_id", "rank", name="uq_ms_preference_rank"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    preference_id: Mapped[int] = mapped_column(ForeignKey("mentor_preference_submissions.id", ondelete="CASCADE"), nullable=False)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)


class MentorDecisionSubmission(Base):
    __tablename__ = "mentor_decision_submissions"
    __table_args__ = (
        UniqueConstraint("batch_id", "teacher_id", "round", "version", name="uq_ms_decision_version"),
        Index("ix_ms_decisions_lookup", "batch_id", "teacher_id", "round", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("mentor_selection_batches.id", ondelete="CASCADE"), nullable=False)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    round: Mapped[str] = mapped_column(String(20), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=DecisionStatus.DRAFT, nullable=False)
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: local_now(), nullable=False)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class MentorDecisionItem(Base):
    __tablename__ = "mentor_decision_items"
    __table_args__ = (UniqueConstraint("submission_id", "student_id", name="uq_ms_decision_student"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("mentor_decision_submissions.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)


class MentorMatchResultVersion(Base):
    __tablename__ = "mentor_match_result_versions"
    __table_args__ = (UniqueConstraint("batch_id", "round", "version", name="uq_ms_result_version"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("mentor_selection_batches.id", ondelete="CASCADE"), nullable=False)
    round: Mapped[str] = mapped_column(String(20), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="calculated", nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: local_now(), nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class MentorMatchResultItem(Base):
    __tablename__ = "mentor_match_result_items"
    __table_args__ = (UniqueConstraint("result_version_id", "student_id", name="uq_ms_result_student"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    result_version_id: Mapped[int] = mapped_column(ForeignKey("mentor_match_result_versions.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    teacher_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    matched_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)


class MentorSelectionTaskRun(Base):
    __tablename__ = "mentor_selection_task_runs"
    __table_args__ = (Index("ix_ms_task_due", "status", "lease_until"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    batch_id: Mapped[int] = mapped_column(ForeignKey("mentor_selection_batches.id", ondelete="CASCADE"), nullable=False)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    round: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    lease_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: local_now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: local_now(), onupdate=lambda: local_now(), nullable=False)


class MentorSelectionNotificationDelivery(Base):
    __tablename__ = "mentor_selection_notification_deliveries"
    __table_args__ = (UniqueConstraint("batch_id", "round", "event_key", "user_id", name="uq_ms_notification_delivery"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("mentor_selection_batches.id", ondelete="CASCADE"), nullable=False)
    round: Mapped[str] = mapped_column(String(20), nullable=False)
    event_key: Mapped[str] = mapped_column(String(100), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    notification_id: Mapped[Optional[int]] = mapped_column(ForeignKey("notifications.id", ondelete="SET NULL"), nullable=True)
    delivered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: local_now(), nullable=False)
