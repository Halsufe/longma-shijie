"""add party tables

Revision ID: i012f3c4d5e6
Revises: h901e2b3c4d5
Create Date: 2026-08-05 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i012f3c4d5e6"
down_revision: Union[str, None] = "h901e2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    columns = sa.inspect(op.get_bind()).get_columns(table_name)
    return any(column["name"] == column_name for column in columns)


def _index_exists(table_name: str, index_name: str) -> bool:
    indexes = sa.inspect(op.get_bind()).get_indexes(table_name)
    return any(index["name"] == index_name for index in indexes)


def upgrade() -> None:
    if not _column_exists("users", "party_json"):
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "party_json",
                    sa.Text(),
                    server_default=sa.text("'{}'"),
                    nullable=False,
                )
            )

    if not _table_exists("party_activities"):
        op.create_table(
            "party_activities",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("category", sa.String(length=30), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("location", sa.String(length=200), nullable=False),
            sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("registration_deadline", sa.DateTime(timezone=True), nullable=True),
            sa.Column("target_roles", sa.String(length=30), nullable=False),
            sa.Column(
                "target_member_ids_json",
                sa.Text(),
                server_default=sa.text("'[]'"),
                nullable=False,
            ),
            sa.Column("max_participants", sa.Integer(), nullable=True),
            sa.Column(
                "materials_json",
                sa.Text(),
                server_default=sa.text("'[]'"),
                nullable=False,
            ),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column(
                "summary_attachments_json",
                sa.Text(),
                server_default=sa.text("'[]'"),
                nullable=False,
            ),
            sa.Column(
                "status",
                sa.String(length=20),
                server_default=sa.text("'draft'"),
                nullable=False,
            ),
            sa.Column("created_by", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _index_exists("party_activities", "ix_party_activities_status_start_at"):
        op.create_index(
            "ix_party_activities_status_start_at",
            "party_activities",
            ["status", "start_at"],
        )
    if not _index_exists("party_activities", "ix_party_activities_category_start_at"):
        op.create_index(
            "ix_party_activities_category_start_at",
            "party_activities",
            ["category", "start_at"],
        )

    if not _table_exists("party_activity_participants"):
        op.create_table(
            "party_activity_participants",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("activity_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column(
                "registration_status",
                sa.String(length=20),
                server_default=sa.text("'registered'"),
                nullable=False,
            ),
            sa.Column(
                "attendance_status",
                sa.String(length=20),
                server_default=sa.text("'none'"),
                nullable=False,
            ),
            sa.Column("sign_in_time", sa.DateTime(timezone=True), nullable=True),
            sa.Column("sign_in_method", sa.String(length=20), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["activity_id"], ["party_activities.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _index_exists("party_activity_participants", "uq_party_participant"):
        op.create_index(
            "uq_party_participant",
            "party_activity_participants",
            ["activity_id", "user_id"],
            unique=True,
        )
    if not _index_exists("party_activity_participants", "ix_party_participant_user"):
        op.create_index(
            "ix_party_participant_user",
            "party_activity_participants",
            ["user_id", "activity_id"],
        )
    if not _index_exists("party_activity_participants", "ix_party_participant_attendance"):
        op.create_index(
            "ix_party_participant_attendance",
            "party_activity_participants",
            ["activity_id", "attendance_status"],
        )

    if not _table_exists("party_materials"):
        op.create_table(
            "party_materials",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("material_type", sa.String(length=30), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("original_name", sa.String(length=255), nullable=False),
            sa.Column("stored_name", sa.String(length=255), nullable=False),
            sa.Column("mime_type", sa.String(length=100), nullable=False),
            sa.Column("size", sa.Integer(), nullable=False),
            sa.Column("uploaded_by", sa.Integer(), nullable=False),
            sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _index_exists("party_materials", "ix_party_materials_user"):
        op.create_index(
            "ix_party_materials_user",
            "party_materials",
            ["user_id", "material_type"],
        )
    if not _index_exists("party_materials", "ix_party_materials_uploaded_at"):
        op.create_index(
            "ix_party_materials_uploaded_at", "party_materials", ["uploaded_at"]
        )


def downgrade() -> None:
    op.drop_index("ix_party_materials_uploaded_at", table_name="party_materials")
    op.drop_index("ix_party_materials_user", table_name="party_materials")
    op.drop_table("party_materials")

    op.drop_index(
        "ix_party_participant_attendance",
        table_name="party_activity_participants",
    )
    op.drop_index(
        "ix_party_participant_user", table_name="party_activity_participants"
    )
    op.drop_index("uq_party_participant", table_name="party_activity_participants")
    op.drop_table("party_activity_participants")

    op.drop_index(
        "ix_party_activities_category_start_at", table_name="party_activities"
    )
    op.drop_index(
        "ix_party_activities_status_start_at", table_name="party_activities"
    )
    op.drop_table("party_activities")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("party_json")
