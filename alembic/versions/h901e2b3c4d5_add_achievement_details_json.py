"""add achievement details json

Revision ID: h901e2b3c4d5
Revises: g890d1a2b3c4
Create Date: 2026-08-05 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h901e2b3c4d5"
down_revision: Union[str, None] = "g890d1a2b3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("achievements", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "details_json",
                sa.Text(),
                server_default=sa.text("'{}'"),
                nullable=False,
            )
        )
        batch_op.create_index(
            "ix_achievements_user_id_achievement_date",
            ["user_id", "achievement_date"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("achievements", schema=None) as batch_op:
        batch_op.drop_index("ix_achievements_user_id_achievement_date")
        batch_op.drop_column("details_json")
