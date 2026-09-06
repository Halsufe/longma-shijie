"""add political status and learning material tables

Revision ID: k2345g6h7i8j
Revises: j1234f5a6b7c
Create Date: 2026-08-06 00:00:00.000000
"""
from datetime import datetime, timezone
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "k2345g6h7i8j"
down_revision: Union[str, None] = "j1234f5a6b7c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PARTY_TYPE_TO_POLITICAL_STATUS = {
    "正式党员": "中共党员",
    "预备党员": "预备党员",
    "入党积极分子": "入党积极分子",
}


def _table_exists(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    return any(
        column["name"] == column_name
        for column in sa.inspect(op.get_bind()).get_columns(table_name)
    )


def _index_exists(table_name: str, index_name: str) -> bool:
    return any(
        index["name"] == index_name
        for index in sa.inspect(op.get_bind()).get_indexes(table_name)
    )


def _political_status(party_json: str | None) -> str:
    try:
        party = json.loads(party_json or "{}")
    except (json.JSONDecodeError, TypeError):
        party = {}
    if not isinstance(party, dict) or party.get("deleted_at"):
        return "群众"
    return PARTY_TYPE_TO_POLITICAL_STATUS.get(party.get("party_type"), "群众")


def upgrade() -> None:
    if not _column_exists("users", "political_status"):
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "political_status",
                    sa.String(length=30),
                    server_default=sa.text("'群众'"),
                    nullable=False,
                )
            )
    if not _column_exists("users", "political_status_updated_at"):
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "political_status_updated_at",
                    sa.DateTime(timezone=True),
                    nullable=True,
                )
            )

    if not _table_exists("political_status_reviews"):
        op.create_table(
            "political_status_reviews",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("from_status", sa.String(length=30), nullable=False),
            sa.Column("to_status", sa.String(length=30), nullable=False),
            sa.Column(
                "status",
                sa.String(length=20),
                server_default=sa.text("'pending'"),
                nullable=False,
            ),
            sa.Column("submitted_by", sa.Integer(), nullable=False),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("reviewed_by", sa.Integer(), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("remark", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
            sa.ForeignKeyConstraint(["submitted_by"], ["users.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _index_exists(
        "political_status_reviews", "ix_political_review_status_submitted"
    ):
        op.create_index(
            "ix_political_review_status_submitted",
            "political_status_reviews",
            ["status", "submitted_at"],
        )
    if not _index_exists(
        "political_status_reviews", "ix_political_review_user"
    ):
        op.create_index(
            "ix_political_review_user",
            "political_status_reviews",
            ["user_id", "status"],
        )

    if not _table_exists("political_materials"):
        op.create_table(
            "political_materials",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column(
                "applicable_roles_json",
                sa.Text(),
                server_default=sa.text("'[]'"),
                nullable=False,
            ),
            sa.Column(
                "target_user_ids_json",
                sa.Text(),
                server_default=sa.text("'[]'"),
                nullable=False,
            ),
            sa.Column(
                "attachments_json",
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
    if not _index_exists(
        "political_materials", "ix_political_materials_status_created"
    ):
        op.create_index(
            "ix_political_materials_status_created",
            "political_materials",
            ["status", "created_at"],
        )
    if not _index_exists(
        "political_materials", "ix_political_materials_created_by"
    ):
        op.create_index(
            "ix_political_materials_created_by",
            "political_materials",
            ["created_by"],
        )

    bind = op.get_bind()
    now = datetime.now(timezone.utc)
    users = bind.execute(
        sa.text(
            "SELECT id, party_json, political_status_updated_at "
            "FROM users"
        )
    ).mappings()
    for user in users:
        political_status = _political_status(user.get("party_json"))
        # The revision is normally executed once by Alembic, but keeping the
        # backfill idempotent protects deployments that re-run migrations
        # manually or resume after a partial failure. Never overwrite a status
        # that has already been initialized or changed by the application.
        if user.get("political_status_updated_at") is None:
            bind.execute(
                sa.text(
                    "UPDATE users SET political_status = :status, "
                    "political_status_updated_at = :updated_at WHERE id = :user_id"
                ),
                {
                    "status": political_status,
                    "updated_at": now,
                    "user_id": user["id"],
                },
            )
        if _table_exists("audit_logs"):
            initialized = bind.execute(
                sa.text(
                    "SELECT 1 FROM audit_logs "
                    "WHERE action = 'political_status_initialize' "
                    "AND target_type = 'user' AND target_id = :target_id "
                    "LIMIT 1"
                ),
                {"target_id": str(user["id"])},
            ).first()
            if initialized is None:
                bind.execute(
                    sa.text(
                        "INSERT INTO audit_logs (operator_id, operator_name, action, "
                        "target_type, target_id, result, detail, created_at) VALUES "
                        "(NULL, 'system', 'political_status_initialize', 'user', "
                        ":target_id, 'success', :detail, :created_at)"
                    ),
                    {
                        "target_id": str(user["id"]),
                        "detail": json.dumps(
                            {"political_status": political_status},
                            ensure_ascii=False,
                        ),
                        "created_at": now,
                    },
                )


def downgrade() -> None:
    bind = op.get_bind()
    if _table_exists("audit_logs"):
        bind.execute(
            sa.text(
                "DELETE FROM audit_logs WHERE action = 'political_status_initialize'"
            )
        )

    if _table_exists("political_materials"):
        if _index_exists(
            "political_materials", "ix_political_materials_created_by"
        ):
            op.drop_index(
                "ix_political_materials_created_by",
                table_name="political_materials",
            )
        if _index_exists(
            "political_materials", "ix_political_materials_status_created"
        ):
            op.drop_index(
                "ix_political_materials_status_created",
                table_name="political_materials",
            )
        op.drop_table("political_materials")

    if _table_exists("political_status_reviews"):
        if _index_exists(
            "political_status_reviews", "ix_political_review_user"
        ):
            op.drop_index(
                "ix_political_review_user", table_name="political_status_reviews"
            )
        if _index_exists(
            "political_status_reviews", "ix_political_review_status_submitted"
        ):
            op.drop_index(
                "ix_political_review_status_submitted",
                table_name="political_status_reviews",
            )
        op.drop_table("political_status_reviews")

    if _column_exists("users", "political_status_updated_at"):
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.drop_column("political_status_updated_at")
    if _column_exists("users", "political_status"):
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.drop_column("political_status")
