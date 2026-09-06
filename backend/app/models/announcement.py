from __future__ import annotations

import enum
import json
from datetime import date, datetime, timedelta

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base, local_now


class AnnouncementSourceStatus(str, enum.Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"


class AnnouncementStatus(str, enum.Enum):
    DISCOVERED = "discovered"
    PROCESSING = "processing"
    READY = "ready"
    PARTIAL = "partial"
    FAILED = "failed"
    EXPIRED = "expired"


class RelevanceStatus(str, enum.Enum):
    RELEVANT = "relevant"
    UNCERTAIN = "uncertain"
    IRRELEVANT = "irrelevant"


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"


class DeliveryStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class AnnouncementSource(Base):
    __tablename__ = "announcement_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    list_url: Mapped[str] = mapped_column(String(500), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    adapter_key: Mapped[str] = mapped_column(String(80), nullable=False)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class SchoolAnnouncement(Base):
    __tablename__ = "school_announcements"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    published_at: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    body_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    summary_text: Mapped[str | None] = mapped_column(Text)
    summary_status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    relevance_status: Mapped[str] = mapped_column(String(30), default=RelevanceStatus.UNCERTAIN.value, nullable=False, index=True)
    relevance_confidence: Mapped[float | None] = mapped_column()
    key_fields_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(30), default=AnnouncementStatus.DISCOVERED.value, nullable=False, index=True)
    first_discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=local_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=local_now, onupdate=local_now, nullable=False)
    key_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retention_until: Mapped[date | None] = mapped_column(Date, index=True)

    @property
    def key_fields(self) -> dict:
        try:
            value = json.loads(self.key_fields_json or "{}")
            return value if isinstance(value, dict) else {}
        except (TypeError, ValueError):
            return {}

    @key_fields.setter
    def key_fields(self, value: dict) -> None:
        self.key_fields_json = json.dumps(value or {}, ensure_ascii=False)

    @staticmethod
    def retention_date(published_at: date) -> date:
        return published_at + timedelta(days=30)

    def is_visible(self, on_date: date | None = None) -> bool:
        today = on_date or local_now().date()
        return self.relevance_status in {RelevanceStatus.RELEVANT.value, RelevanceStatus.UNCERTAIN.value} and self.status in {
            AnnouncementStatus.READY.value, AnnouncementStatus.PARTIAL.value,
        } and (self.retention_until is None or today <= self.retention_until)


class AnnouncementOrigin(Base):
    __tablename__ = "announcement_origins"
    id: Mapped[int] = mapped_column(primary_key=True)
    announcement_id: Mapped[int] = mapped_column(ForeignKey("school_announcements.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("announcement_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    canonical_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_title: Mapped[str | None] = mapped_column(String(500))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=local_now, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=local_now, onupdate=local_now, nullable=False)
    __table_args__ = (UniqueConstraint("source_id", "canonical_url", name="uq_announcement_origin_source_url"),)


class AnnouncementAttachment(Base):
    __tablename__ = "announcement_attachments"
    id: Mapped[int] = mapped_column(primary_key=True)
    announcement_id: Mapped[int] = mapped_column(ForeignKey("school_announcements.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    media_type: Mapped[str | None] = mapped_column(String(100))
    parsed_text: Mapped[str | None] = mapped_column(Text)
    parse_status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    error_summary: Mapped[str | None] = mapped_column(String(500))
    __table_args__ = (UniqueConstraint("announcement_id", "url", name="uq_announcement_attachment_url"),)


class AnnouncementTaskRun(Base):
    __tablename__ = "announcement_task_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    task_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default=TaskStatus.PENDING.value, nullable=False, index=True)
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_owner: Mapped[str | None] = mapped_column(String(100))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discovered_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retry_of_id: Mapped[int | None] = mapped_column(ForeignKey("announcement_task_runs.id"))
    error_summary: Mapped[str | None] = mapped_column(Text)
    manual: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=local_now, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AnnouncementDigest(Base):
    __tablename__ = "announcement_digests"
    id: Mapped[int] = mapped_column(primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    snapshot_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    notification_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    is_recovery: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=local_now, nullable=False)
    __table_args__ = (UniqueConstraint("window_start", "window_end", name="uq_announcement_digest_window"),)


class AnnouncementDigestDelivery(Base):
    __tablename__ = "announcement_digest_deliveries"
    id: Mapped[int] = mapped_column(primary_key=True)
    digest_id: Mapped[int] = mapped_column(ForeignKey("announcement_digests.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default=DeliveryStatus.PENDING.value, nullable=False)
    notification_id: Mapped[int | None] = mapped_column(ForeignKey("notifications.id", ondelete="SET NULL"))
    error_summary: Mapped[str | None] = mapped_column(String(500))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("digest_id", "user_id", name="uq_announcement_digest_delivery_user"),
        Index("ix_announcement_delivery_status", "digest_id", "status"),
    )

