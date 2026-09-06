"""add general platform tables

Revision ID: l2345m6n7o8p
Revises: l3456h7i8j9k
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "l2345m6n7o8p"
down_revision: Union[str, None] = "l3456h7i8j9k"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    tables = _tables()
    if "knowledge_folders" not in tables:
        op.create_table("knowledge_folders",
            sa.Column("id", sa.Integer(), primary_key=True), sa.Column("scope", sa.String(20), nullable=False),
            sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("name", sa.String(100), nullable=False), sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True)),
        )
    if "knowledge_files" in tables and "folder_id" not in _columns("knowledge_files"):
        with op.batch_alter_table("knowledge_files") as batch:
            batch.add_column(sa.Column("folder_id", sa.Integer(), sa.ForeignKey("knowledge_folders.id"), nullable=True))
            batch.create_index("ix_knowledge_files_folder_id", ["folder_id"])
    if "knowledge_file_versions" not in tables:
        op.create_table("knowledge_file_versions",
            sa.Column("id", sa.Integer(), primary_key=True), sa.Column("file_id", sa.Integer(), sa.ForeignKey("knowledge_files.id"), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False), sa.Column("stored_name", sa.String(255), nullable=False), sa.Column("original_name", sa.String(255), nullable=False),
            sa.Column("mime_type", sa.String(100), nullable=False), sa.Column("size", sa.Integer(), nullable=False), sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        )
    if "assignment_attachments" not in tables:
        op.create_table("assignment_attachments", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("assignments.id"), nullable=False), sa.Column("original_name", sa.String(255), nullable=False), sa.Column("stored_name", sa.String(255), nullable=False), sa.Column("mime_type", sa.String(100), nullable=False), sa.Column("size", sa.Integer(), nullable=False), sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("deleted_at", sa.DateTime(timezone=True)))
        op.create_index("ix_assignment_attachments_assignment_id", "assignment_attachments", ["assignment_id"])
    if "submission_attachments" not in tables:
        op.create_table("submission_attachments", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("submission_id", sa.Integer(), sa.ForeignKey("submissions.id"), nullable=False), sa.Column("version", sa.Integer(), nullable=False), sa.Column("original_name", sa.String(255), nullable=False), sa.Column("stored_name", sa.String(255), nullable=False), sa.Column("mime_type", sa.String(100), nullable=False), sa.Column("size", sa.Integer(), nullable=False), sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
        op.create_index("ix_submission_attachments_submission_id", "submission_attachments", ["submission_id"])
        op.create_index("ix_submission_attachments_version", "submission_attachments", ["version"])
    if "chat_message_attachments" not in tables:
        op.create_table("chat_message_attachments", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("message_id", sa.Integer(), sa.ForeignKey("chat_messages.id"), nullable=False), sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("original_name", sa.String(255), nullable=False), sa.Column("stored_name", sa.String(255), nullable=False), sa.Column("mime_type", sa.String(100), nullable=False), sa.Column("size", sa.Integer(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
        op.create_index("ix_chat_message_attachments_message_id", "chat_message_attachments", ["message_id"])
        op.create_index("ix_chat_message_attachments_owner_user_id", "chat_message_attachments", ["owner_user_id"])
    if "chat_messages" in tables and "regenerated_at" not in _columns("chat_messages"):
        with op.batch_alter_table("chat_messages") as batch:
            batch.add_column(sa.Column("regenerated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    for table in ("chat_message_attachments", "submission_attachments", "assignment_attachments"):
        if table in tables:
            op.drop_table(table)
    if "chat_messages" in tables and "regenerated_at" in _columns("chat_messages"):
        with op.batch_alter_table("chat_messages") as batch:
            batch.drop_column("regenerated_at")
