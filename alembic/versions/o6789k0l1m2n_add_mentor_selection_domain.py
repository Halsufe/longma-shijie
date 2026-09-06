"""add academic mentor selection domain tables

Revision ID: o6789k0l1m2n
Revises: n5678j9k0l1m
"""
from typing import Sequence, Union

from alembic import op

from backend.app.models.mentor_selection import (
    MentorDecisionItem,
    MentorDecisionSubmission,
    MentorMatchResultItem,
    MentorMatchResultVersion,
    MentorPreferenceItem,
    MentorPreferenceSubmission,
    MentorSelectionBatch,
    MentorSelectionBatchMentor,
    MentorSelectionBatchStudent,
    MentorSelectionNotificationDelivery,
    MentorSelectionTaskRun,
)
revision: str = "o6789k0l1m2n"
down_revision: Union[str, None] = "n5678j9k0l1m"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = (
    MentorSelectionBatch.__table__,
    MentorSelectionBatchStudent.__table__,
    MentorSelectionBatchMentor.__table__,
    MentorPreferenceSubmission.__table__,
    MentorPreferenceItem.__table__,
    MentorDecisionSubmission.__table__,
    MentorDecisionItem.__table__,
    MentorMatchResultVersion.__table__,
    MentorMatchResultItem.__table__,
    MentorSelectionTaskRun.__table__,
    MentorSelectionNotificationDelivery.__table__,
)


def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        table.create(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(TABLES):
        table.drop(bind, checkfirst=True)
