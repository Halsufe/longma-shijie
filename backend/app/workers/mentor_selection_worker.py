"""Independent scheduler for mentor selection phase transitions.

Run once for operations/testing with ``python -m ... --once``.  The web
process intentionally never starts this loop.
"""
import argparse
import logging
import time
from datetime import datetime

from sqlalchemy.orm import Session

from backend.app.core.database import SessionLocal, local_now
from backend.app.models.mentor_selection import (
    BatchStatus,
    MentorMatchResultItem,
    MentorMatchResultVersion,
    MentorSelectionBatch,
    SelectionRound,
)
from backend.app.services.mentor_selection_service import (
    BatchStateMachine,
    MatchService,
    PreferenceService,
    RosterService,
)

log = logging.getLogger(__name__)
POLL_INTERVAL_SECONDS = 60


def _reached(value: datetime | None, now: datetime) -> bool:
    if value is None:
        return False
    if value.tzinfo is None:
        value = value.replace(tzinfo=now.tzinfo)
    return now >= value


def process_due_batches(db: Session, now: datetime | None = None) -> int:
    now = now or local_now()
    changed = 0
    batches = db.query(MentorSelectionBatch).filter(
        MentorSelectionBatch.deleted_at.is_(None),
        MentorSelectionBatch.status != BatchStatus.COMPLETED,
    ).order_by(MentorSelectionBatch.id).all()
    for batch in batches:
        try:
            if batch.status == BatchStatus.DRAFT and _reached(batch.student_apply_start, now):
                RosterService.can_open_main(batch, db)
                BatchStateMachine.move(batch, BatchStatus.STUDENT_APPLY)
            elif batch.status == BatchStatus.STUDENT_APPLY and _reached(batch.student_apply_end, now):
                PreferenceService.lock(db, batch.id, SelectionRound.MAIN)
                BatchStateMachine.move(batch, BatchStatus.MENTOR_SELECT)
            elif batch.status == BatchStatus.MENTOR_SELECT and _reached(batch.mentor_select_end, now):
                MatchService.calculate(db, batch, SelectionRound.MAIN)
                BatchStateMachine.move(batch, BatchStatus.MAIN_PENDING)
            elif batch.status == BatchStatus.MAIN_PENDING and _reached(batch.main_publish_at, now):
                result = _latest_result(db, batch.id, SelectionRound.MAIN)
                if result:
                    MatchService.publish(db, result, batch)
                    BatchStateMachine.move(batch, BatchStatus.MAIN_PUBLISHED)
            elif batch.status == BatchStatus.MAIN_PUBLISHED and _reached(batch.supplement_student_start, now):
                BatchStateMachine.move(batch, BatchStatus.SUPPLEMENT_STUDENT_APPLY)
            elif batch.status == BatchStatus.SUPPLEMENT_STUDENT_APPLY and _reached(batch.supplement_student_end, now):
                PreferenceService.lock(db, batch.id, SelectionRound.SUPPLEMENT)
                BatchStateMachine.move(batch, BatchStatus.SUPPLEMENT_MENTOR_SELECT)
            elif batch.status == BatchStatus.SUPPLEMENT_MENTOR_SELECT and _reached(batch.supplement_mentor_end, now):
                result = MatchService.calculate(db, batch, SelectionRound.SUPPLEMENT)
                unmatched = db.query(MentorMatchResultItem).filter_by(
                    result_version_id=result.id, status="unmatched"
                ).count()
                BatchStateMachine.move(
                    batch,
                    BatchStatus.SUPPLEMENT_BLOCKED if unmatched else BatchStatus.SUPPLEMENT_PENDING,
                )
            elif batch.status == BatchStatus.SUPPLEMENT_PENDING and _reached(batch.supplement_publish_at, now):
                result = _latest_result(db, batch.id, SelectionRound.SUPPLEMENT)
                if result:
                    MatchService.publish(db, result, batch)
                    BatchStateMachine.move(batch, BatchStatus.SUPPLEMENT_PUBLISHED)
                    BatchStateMachine.move(batch, BatchStatus.COMPLETED)
            else:
                continue
            batch.version_no += 1
            db.commit()
            changed += 1
        except Exception:
            db.rollback()
            log.exception("mentor selection task failed for batch %s", batch.id)
    return changed


def _latest_result(db: Session, batch_id: int, round_name: str) -> MentorMatchResultVersion | None:
    return db.query(MentorMatchResultVersion).filter_by(
        batch_id=batch_id, round=round_name
    ).order_by(MentorMatchResultVersion.version.desc()).first()


def main() -> None:
    parser = argparse.ArgumentParser(description="Academic mentor selection scheduler")
    parser.add_argument("--once", action="store_true", help="scan once and exit")
    args = parser.parse_args()
    from backend.app.core.config import settings
    if settings.DB_URL.endswith(":memory:"):
        # Importing the application registers every model and creates the
        # ephemeral schema used by --once smoke tests.
        from backend.app.main import app as _app
    while True:
        with SessionLocal() as db:
            process_due_batches(db)
        if args.once:
            return
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
