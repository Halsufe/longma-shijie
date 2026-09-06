"""add chat scope, recovery, citations, and token quota

Revision ID: p7890q1r2s3
Revises: o6789k0l1m2n
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from backend.app.models.token_quota import (
    ChatTokenUsageEvent,
    TokenQuotaAuditLog,
    TokenQuotaPolicy,
    UserDailyTokenUsage,
    UserTokenQuotaOverride,
)

revision: str = "p7890q1r2s3"
down_revision: Union[str, None] = "o6789k0l1m2n"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(bind, table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    for table in (
        TokenQuotaPolicy.__table__,
        UserTokenQuotaOverride.__table__,
        UserDailyTokenUsage.__table__,
        ChatTokenUsageEvent.__table__,
        TokenQuotaAuditLog.__table__,
    ):
        table.create(bind, checkfirst=True)

    if "chat_token_usage_events" in tables:
        event_columns = _column_names(bind, "chat_token_usage_events")
        if "reserved_tokens" not in event_columns:
            with op.batch_alter_table("chat_token_usage_events") as batch:
                batch.add_column(
                    sa.Column("reserved_tokens", sa.Integer(), nullable=False, server_default="0")
                )

    session_columns = _column_names(bind, "chat_sessions")
    with op.batch_alter_table("chat_sessions") as batch:
        if "knowledge_scope" not in session_columns:
            batch.add_column(
                sa.Column("knowledge_scope", sa.String(20), nullable=False, server_default="personal")
            )
        if "web_search_enabled" not in session_columns:
            batch.add_column(
                sa.Column("web_search_enabled", sa.Boolean(), nullable=False, server_default=sa.true())
            )
        if "last_message_status" not in session_columns:
            batch.add_column(sa.Column("last_message_status", sa.String(30), nullable=True))

    message_columns = _column_names(bind, "chat_messages")
    with op.batch_alter_table("chat_messages") as batch:
        for column in (
            sa.Column("knowledge_scope", sa.String(20), nullable=True),
            sa.Column("request_id", sa.String(64), nullable=True),
            sa.Column("status", sa.String(30), nullable=False, server_default="completed"),
            sa.Column("partial_content", sa.Text(), nullable=True),
            sa.Column("last_event_id", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_code", sa.String(80), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("input_tokens", sa.Integer(), nullable=True),
            sa.Column("output_tokens", sa.Integer(), nullable=True),
            sa.Column("total_tokens", sa.Integer(), nullable=True),
        ):
            if column.name not in message_columns:
                batch.add_column(column)

    knowledge_columns = _column_names(bind, "knowledge_files")
    if "class_id" not in knowledge_columns:
        with op.batch_alter_table("knowledge_files") as batch:
            batch.add_column(sa.Column("class_id", sa.Integer(), nullable=True))
            batch.create_index("ix_knowledge_files_class_id", ["class_id"], unique=False)

    tables = set(sa.inspect(bind).get_table_names())
    if "chat_requests" not in tables:
        op.create_table(
            "chat_requests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("request_id", sa.String(64), nullable=False, unique=True),
            sa.Column("session_id", sa.Integer(), sa.ForeignKey("chat_sessions.id"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("message_id", sa.Integer(), sa.ForeignKey("chat_messages.id"), nullable=True),
            sa.Column("parent_request_id", sa.String(64), nullable=True),
            sa.Column("idempotency_key", sa.String(200), nullable=False),
            sa.Column("model", sa.String(100), nullable=False, server_default="deepseek-v4-flash"),
            sa.Column("knowledge_scope", sa.String(20), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
            sa.Column("last_event_id", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("partial_content", sa.Text(), nullable=True),
            sa.Column("input_content", sa.Text(), nullable=True),
            sa.Column("usage_status", sa.String(40), nullable=True),
            sa.Column("error_code", sa.String(80), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("user_id", "idempotency_key", name="uq_chat_request_idempotency"),
        )
        op.create_index("ix_chat_requests_user_status", "chat_requests", ["user_id", "status"])
    elif "input_content" not in _column_names(bind, "chat_requests"):
        with op.batch_alter_table("chat_requests") as batch:
            batch.add_column(sa.Column("input_content", sa.Text(), nullable=True))

    if "chat_message_citations" not in tables:
        op.create_table(
            "chat_message_citations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("message_id", sa.Integer(), sa.ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_type", sa.String(20), nullable=False),
            sa.Column("scope", sa.String(20), nullable=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("class_id", sa.Integer(), nullable=True),
            sa.Column("knowledge_base_name", sa.String(200), nullable=True),
            sa.Column("document_id", sa.Integer(), nullable=True),
            sa.Column("document_name", sa.String(255), nullable=True),
            sa.Column("source_title", sa.String(500), nullable=True),
            sa.Column("source_url", sa.String(2000), nullable=True),
            sa.Column("matched_excerpt", sa.Text(), nullable=True),
            sa.Column("rank", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint(
                "message_id", "source_type", "source_url", "document_id", "rank",
                name="uq_chat_citation_identity",
            ),
        )
        op.create_index(
            "ix_chat_citations_message_rank", "chat_message_citations", ["message_id", "rank"]
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    for name in ("chat_message_citations", "chat_requests"):
        if name in tables:
            op.drop_table(name)
    for table in reversed(
        (
            TokenQuotaAuditLog.__table__,
            ChatTokenUsageEvent.__table__,
            UserDailyTokenUsage.__table__,
            UserTokenQuotaOverride.__table__,
            TokenQuotaPolicy.__table__,
        )
    ):
        table.drop(bind, checkfirst=True)

    if "chat_messages" in tables:
        with op.batch_alter_table("chat_messages") as batch:
            for name in (
                "total_tokens", "output_tokens", "input_tokens", "completed_at", "error_message",
                "error_code", "last_event_id", "partial_content", "status", "request_id", "knowledge_scope",
            ):
                if name in _column_names(bind, "chat_messages"):
                    batch.drop_column(name)
    if "chat_sessions" in tables:
        with op.batch_alter_table("chat_sessions") as batch:
            for name in ("last_message_status", "web_search_enabled", "knowledge_scope"):
                if name in _column_names(bind, "chat_sessions"):
                    batch.drop_column(name)
    if "knowledge_files" in tables and "class_id" in _column_names(bind, "knowledge_files"):
        with op.batch_alter_table("knowledge_files") as batch:
            batch.drop_index("ix_knowledge_files_class_id")
            batch.drop_column("class_id")
