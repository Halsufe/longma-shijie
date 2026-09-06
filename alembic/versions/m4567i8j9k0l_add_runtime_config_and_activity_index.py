"""add runtime config and activity query index

Revision ID: m4567i8j9k0l
Revises: l2345m6n7o8p
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "m4567i8j9k0l"
down_revision: Union[str, None] = "l2345m6n7o8p"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _indexes(table: str) -> set[str]:
    return {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    if "runtime_configs" not in _tables():
        op.create_table(
            "runtime_configs",
            sa.Column("key", sa.String(length=100), nullable=False),
            sa.Column("value_json", sa.Text(), nullable=False),
            sa.Column("updated_by", sa.Integer(), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("key"),
        )
    if "user_sessions" in _tables() and "ix_user_sessions_user_id_last_active_at" not in _indexes("user_sessions"):
        op.create_index("ix_user_sessions_user_id_last_active_at", "user_sessions", ["user_id", "last_active_at"])
    tables = _tables()
    if "announcement_sources" not in tables:
        op.create_table("announcement_sources", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("code", sa.String(50), nullable=False, unique=True), sa.Column("name", sa.String(120), nullable=False), sa.Column("list_url", sa.String(500), nullable=False), sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"), sa.Column("adapter_key", sa.String(80), nullable=False), sa.Column("last_success_at", sa.DateTime(timezone=True)), sa.Column("last_failure_at", sa.DateTime(timezone=True)), sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"))
    if "school_announcements" not in tables:
        op.create_table("school_announcements", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("title", sa.String(500), nullable=False), sa.Column("published_at", sa.Date(), nullable=False), sa.Column("body_text", sa.Text(), nullable=False, server_default=""), sa.Column("summary_text", sa.Text()), sa.Column("summary_status", sa.String(30), nullable=False, server_default="pending"), sa.Column("relevance_status", sa.String(30), nullable=False, server_default="uncertain"), sa.Column("relevance_confidence", sa.Float()), sa.Column("key_fields_json", sa.Text(), nullable=False, server_default="{}"), sa.Column("content_hash", sa.String(64)), sa.Column("status", sa.String(30), nullable=False, server_default="discovered"), sa.Column("first_discovered_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("key_updated_at", sa.DateTime(timezone=True)), sa.Column("retention_until", sa.Date()))
    if "announcement_origins" not in tables:
        op.create_table("announcement_origins", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("announcement_id", sa.Integer(), sa.ForeignKey("school_announcements.id", ondelete="CASCADE"), nullable=False), sa.Column("source_id", sa.Integer(), sa.ForeignKey("announcement_sources.id", ondelete="CASCADE"), nullable=False), sa.Column("canonical_url", sa.String(1000), nullable=False), sa.Column("source_title", sa.String(500)), sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False), sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("source_id", "canonical_url", name="uq_announcement_origin_source_url"))
    if "announcement_attachments" not in tables:
        op.create_table("announcement_attachments", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("announcement_id", sa.Integer(), sa.ForeignKey("school_announcements.id", ondelete="CASCADE"), nullable=False), sa.Column("name", sa.String(500), nullable=False), sa.Column("url", sa.String(1000), nullable=False), sa.Column("media_type", sa.String(100)), sa.Column("parsed_text", sa.Text()), sa.Column("parse_status", sa.String(30), nullable=False, server_default="pending"), sa.Column("error_summary", sa.String(500)), sa.UniqueConstraint("announcement_id", "url", name="uq_announcement_attachment_url"))
    if "announcement_task_runs" not in tables:
        op.create_table("announcement_task_runs", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("task_key", sa.String(200), nullable=False, unique=True), sa.Column("task_type", sa.String(40), nullable=False), sa.Column("status", sa.String(30), nullable=False, server_default="pending"), sa.Column("window_start", sa.DateTime(timezone=True)), sa.Column("window_end", sa.DateTime(timezone=True)), sa.Column("lease_owner", sa.String(100)), sa.Column("lease_until", sa.DateTime(timezone=True)), sa.Column("heartbeat_at", sa.DateTime(timezone=True)), sa.Column("discovered_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("created_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("retry_of_id", sa.Integer(), sa.ForeignKey("announcement_task_runs.id")), sa.Column("error_summary", sa.Text()), sa.Column("manual", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("finished_at", sa.DateTime(timezone=True)))
    if "announcement_digests" not in tables:
        op.create_table("announcement_digests", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("window_start", sa.DateTime(timezone=True), nullable=False), sa.Column("window_end", sa.DateTime(timezone=True), nullable=False), sa.Column("snapshot_json", sa.Text(), nullable=False, server_default="[]"), sa.Column("notification_text", sa.Text(), nullable=False), sa.Column("status", sa.String(30), nullable=False, server_default="pending"), sa.Column("is_recovery", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("window_start", "window_end", name="uq_announcement_digest_window"))
    if "announcement_digest_deliveries" not in tables:
        op.create_table("announcement_digest_deliveries", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("digest_id", sa.Integer(), sa.ForeignKey("announcement_digests.id", ondelete="CASCADE"), nullable=False), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("status", sa.String(30), nullable=False, server_default="pending"), sa.Column("notification_id", sa.Integer(), sa.ForeignKey("notifications.id", ondelete="SET NULL")), sa.Column("error_summary", sa.String(500)), sa.Column("sent_at", sa.DateTime(timezone=True)), sa.UniqueConstraint("digest_id", "user_id", name="uq_announcement_digest_delivery_user"))


def downgrade() -> None:
    if "user_sessions" in _tables() and "ix_user_sessions_user_id_last_active_at" in _indexes("user_sessions"):
        op.drop_index("ix_user_sessions_user_id_last_active_at", table_name="user_sessions")
    if "runtime_configs" in _tables():
        op.drop_table("runtime_configs")
    for table in ("announcement_digest_deliveries", "announcement_digests", "announcement_task_runs", "announcement_attachments", "announcement_origins", "school_announcements", "announcement_sources"):
        if table in _tables():
            op.drop_table(table)
