from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.app.core.database import local_now
from backend.app.models.announcement import AnnouncementTaskRun, TaskStatus
from backend.app.services.announcement_digest_service import AnnouncementDigestService


def task_key(task_type: str, at: datetime | None = None) -> str:
    stamp = (at or local_now()).strftime("%Y%m%dT%H%M%S%z")
    return f"{task_type}:{stamp}"


def claim_task(db: Session, task_type: str, *, at: datetime | None = None, lease_minutes: int = 30) -> AnnouncementTaskRun | None:
    key = task_key(task_type, at)
    existing = db.query(AnnouncementTaskRun).filter(AnnouncementTaskRun.task_key == key).first()
    if existing and existing.status == TaskStatus.RUNNING.value and existing.lease_until and existing.lease_until > local_now():
        return None
    if existing:
        existing.status = TaskStatus.RUNNING.value
        existing.lease_until = local_now() + timedelta(minutes=lease_minutes)
        existing.heartbeat_at = local_now()
    else:
        existing = AnnouncementTaskRun(task_key=key, task_type=task_type, status=TaskStatus.RUNNING.value, lease_owner=str(uuid4()), lease_until=local_now() + timedelta(minutes=lease_minutes), heartbeat_at=local_now())
        db.add(existing)
    db.commit()
    db.refresh(existing)
    return existing


def run_digest_once(db: Session) -> AnnouncementTaskRun | None:
    task = claim_task(db, "digest")
    if not task:
        return None
    try:
        digest = AnnouncementDigestService.build(db)
        task.status = TaskStatus.SUCCESS.value
        task.created_count = 1
        task.finished_at = local_now()
        task.error_summary = f"digest_id={digest.id}"
    except Exception as exc:
        task.status = TaskStatus.FAILED.value
        task.error_summary = str(exc)[:500]
        task.finished_at = local_now()
    db.commit()
    return task

