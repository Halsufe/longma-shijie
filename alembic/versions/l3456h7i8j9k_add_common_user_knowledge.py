"""add common user center and knowledge base tables

Revision ID: l3456h7i8j9k
Revises: k2345g6h7i8j
Create Date: 2026-08-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "l3456h7i8j9k"
down_revision: Union[str, None] = "k2345g6h7i8j"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "alumni_conversion_requests" not in tables:
        op.create_table(
        "alumni_conversion_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("graduation_year", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("review_comment", sa.Text()),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
        op.create_index("ix_alumni_conversion_requests_user_id", "alumni_conversion_requests", ["user_id"])
        op.create_index("ix_alumni_conversion_requests_status", "alumni_conversion_requests", ["status"])
    if "knowledge_folders" not in tables:
        op.create_table(
        "knowledge_folders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
        op.create_index("ix_knowledge_folders_scope_owner_name", "knowledge_folders", ["scope", "owner_user_id", "name"])
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("knowledge_files")}
    if "folder_id" not in columns:
        with op.batch_alter_table("knowledge_files") as batch_op:
            batch_op.add_column(sa.Column("folder_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key("fk_knowledge_files_folder_id", "knowledge_folders", ["folder_id"], ["id"])
            batch_op.create_index("ix_knowledge_files_folder_id", ["folder_id"])
    if "knowledge_file_versions" not in tables:
        op.create_table(
        "knowledge_file_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("file_id", sa.Integer(), sa.ForeignKey("knowledge_files.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("stored_name", sa.String(255), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("file_id", "version", name="uq_knowledge_file_versions_file_version"),
    )
        op.create_index("ix_knowledge_file_versions_file_id", "knowledge_file_versions", ["file_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if "knowledge_file_versions" in sa.inspect(bind).get_table_names():
        op.drop_table("knowledge_file_versions")
    with op.batch_alter_table("knowledge_files") as batch_op:
        batch_op.drop_index("ix_knowledge_files_folder_id")
        batch_op.drop_constraint("fk_knowledge_files_folder_id", type_="foreignkey")
        batch_op.drop_column("folder_id")
    op.drop_table("knowledge_folders")
    op.drop_table("alumni_conversion_requests")
