"""add skill embeddings

Revision ID: j1234f5a6b7c
Revises: i012f3c4d5e6
Create Date: 2026-08-05 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "j1234f5a6b7c"
down_revision: Union[str, None] = "i012f3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    indexes = sa.inspect(op.get_bind()).get_indexes(table_name)
    return any(index["name"] == index_name for index in indexes)


def upgrade() -> None:
    if not _table_exists("skill_embeddings"):
        op.create_table(
            "skill_embeddings",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("entity_type", sa.String(length=40), nullable=False),
            sa.Column("entity_id", sa.Integer(), nullable=False),
            sa.Column("source_text", sa.Text(), nullable=False),
            sa.Column("embedding_json", sa.Text(), nullable=False),
            sa.Column("version", sa.Integer(), server_default="1", nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("entity_type", "entity_id", name="uq_skill_embedding_entity"),
        )
    if not _index_exists("skill_embeddings", "ix_skill_embeddings_entity_type"):
        op.create_index(
            "ix_skill_embeddings_entity_type", "skill_embeddings", ["entity_type"]
        )
    if not _index_exists("skill_embeddings", "ix_skill_embeddings_type_updated"):
        op.create_index(
            "ix_skill_embeddings_type_updated",
            "skill_embeddings",
            ["entity_type", "updated_at"],
        )


def downgrade() -> None:
    op.drop_index("ix_skill_embeddings_type_updated", table_name="skill_embeddings")
    op.drop_index("ix_skill_embeddings_entity_type", table_name="skill_embeddings")
    op.drop_table("skill_embeddings")
