"""add_v2_campusmate_tables

Revision ID: g890d1a2b3c4
Revises: f5b2c4d6e7a8
Create Date: 2026-08-03 14:00:00.000000

CampusMate v2.0 业务表：在 users 表新增 2 列，创建 achievements / resources /
resource_favorites / resource_likes / teacher_directions /
communication_applications / learning_plans 七张表。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "g890d1a2b3c4"
down_revision: Union[str, None] = "f5b2c4d6e7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users: 新增 graduation_year / profile_json ---
    op.add_column("users", sa.Column("graduation_year", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("profile_json", sa.Text(), nullable=True))

    # --- achievements ---
    op.create_table(
        "achievements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("achievement_date", sa.String(length=20), nullable=True),
        sa.Column("level", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("is_public", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("member_ids_json", sa.Text(), nullable=True),
        sa.Column("proofs_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_achievements_user_id", "achievements", ["user_id"])
    op.create_index("ix_achievements_category", "achievements", ["category"])
    op.create_index("ix_achievements_status", "achievements", ["status"])

    # --- resources ---
    op.create_table(
        "resources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("tags_json", sa.Text(), nullable=True),
        sa.Column("attachments_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'approved'"), nullable=False),
        sa.Column("view_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("like_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_resources_author_id", "resources", ["author_id"])
    op.create_index("ix_resources_type", "resources", ["type"])
    op.create_index("ix_resources_status", "resources", ["status"])

    # --- resource_favorites ---
    op.create_table(
        "resource_favorites",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resource_id"], ["resources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "resource_id", name="uq_resource_favorites_user_resource"),
    )
    op.create_index("ix_resource_favorites_user_id", "resource_favorites", ["user_id"])
    op.create_index("ix_resource_favorites_resource_id", "resource_favorites", ["resource_id"])

    # --- resource_likes ---
    op.create_table(
        "resource_likes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resource_id"], ["resources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "resource_id", name="uq_resource_likes_user_resource"),
    )
    op.create_index("ix_resource_likes_user_id", "resource_likes", ["user_id"])
    op.create_index("ix_resource_likes_resource_id", "resource_likes", ["resource_id"])

    # --- teacher_directions ---
    op.create_table(
        "teacher_directions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tags_json", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["teacher_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_teacher_directions_teacher_id", "teacher_directions", ["teacher_id"])
    op.create_index("ix_teacher_directions_is_active", "teacher_directions", ["is_active"])

    # --- communication_applications ---
    op.create_table(
        "communication_applications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.Column("direction_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("related_achievement_id", sa.Integer(), nullable=True),
        sa.Column("related_resource_id", sa.Integer(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["teacher_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["direction_id"], ["teacher_directions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["related_achievement_id"], ["achievements.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["related_resource_id"], ["resources.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_comm_applications_student_id", "communication_applications", ["student_id"])
    op.create_index("ix_comm_applications_teacher_id", "communication_applications", ["teacher_id"])
    op.create_index("ix_comm_applications_status", "communication_applications", ["status"])
    op.create_index("ix_comm_applications_direction_id", "communication_applications", ["direction_id"])

    # --- learning_plans ---
    op.create_table(
        "learning_plans",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("items_json", sa.Text(), nullable=True),
        sa.Column("reminder_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_completed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_learning_plans_user_id", "learning_plans", ["user_id"])
    op.create_index("ix_learning_plans_is_completed", "learning_plans", ["is_completed"])


def downgrade() -> None:
    # --- learning_plans ---
    op.drop_index("ix_learning_plans_is_completed", table_name="learning_plans")
    op.drop_index("ix_learning_plans_user_id", table_name="learning_plans")
    op.drop_table("learning_plans")

    # --- communication_applications ---
    op.drop_index("ix_comm_applications_direction_id", table_name="communication_applications")
    op.drop_index("ix_comm_applications_status", table_name="communication_applications")
    op.drop_index("ix_comm_applications_teacher_id", table_name="communication_applications")
    op.drop_index("ix_comm_applications_student_id", table_name="communication_applications")
    op.drop_table("communication_applications")

    # --- teacher_directions ---
    op.drop_index("ix_teacher_directions_is_active", table_name="teacher_directions")
    op.drop_index("ix_teacher_directions_teacher_id", table_name="teacher_directions")
    op.drop_table("teacher_directions")

    # --- resource_likes ---
    op.drop_index("ix_resource_likes_resource_id", table_name="resource_likes")
    op.drop_index("ix_resource_likes_user_id", table_name="resource_likes")
    op.drop_table("resource_likes")

    # --- resource_favorites ---
    op.drop_index("ix_resource_favorites_resource_id", table_name="resource_favorites")
    op.drop_index("ix_resource_favorites_user_id", table_name="resource_favorites")
    op.drop_table("resource_favorites")

    # --- resources ---
    op.drop_index("ix_resources_status", table_name="resources")
    op.drop_index("ix_resources_type", table_name="resources")
    op.drop_index("ix_resources_author_id", table_name="resources")
    op.drop_table("resources")

    # --- achievements ---
    op.drop_index("ix_achievements_status", table_name="achievements")
    op.drop_index("ix_achievements_category", table_name="achievements")
    op.drop_index("ix_achievements_user_id", table_name="achievements")
    op.drop_table("achievements")

    # --- users: 移除 graduation_year / profile_json ---
    op.drop_column("users", "profile_json")
    op.drop_column("users", "graduation_year")