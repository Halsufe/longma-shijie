"""add school announcement domain tables

Revision ID: n5678j9k0l1m
Revises: m4567i8j9k0l
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from backend.app.models.announcement import (
    AnnouncementAttachment,
    AnnouncementDigest,
    AnnouncementDigestDelivery,
    AnnouncementOrigin,
    AnnouncementSource,
    AnnouncementTaskRun,
    SchoolAnnouncement,
)

revision: str = "n5678j9k0l1m"
down_revision: Union[str, None] = "m4567i8j9k0l"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = (
    AnnouncementSource.__table__,
    SchoolAnnouncement.__table__,
    AnnouncementOrigin.__table__,
    AnnouncementAttachment.__table__,
    AnnouncementTaskRun.__table__,
    AnnouncementDigest.__table__,
    AnnouncementDigestDelivery.__table__,
)


def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        table.create(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    for table in reversed(TABLES):
        if table.name in existing:
            table.drop(bind)
