from __future__ import annotations

from pathlib import Path
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.app.core.database import local_now
from backend.app.repositories.announcement_repo import AnnouncementRepository


def cleanup_announcements(db: Session, *, today=None, batch_size: int = 100) -> dict[str, int]:
    expired = AnnouncementRepository.find_expired(db, today=today, limit=batch_size)
    deleted = 0
    for item in expired:
        try:
            AnnouncementRepository.mark_expired_and_cleanup(db, item)
            deleted += 1
        except Exception:
            db.rollback()
    db.commit()
    return {"scanned": len(expired), "expired": deleted, "failed": len(expired) - deleted}


def cleanup_temporary_files(root: str | Path, *, ttl_seconds: int = 3600) -> int:
    base = Path(root).resolve()
    if not base.exists() or not base.is_dir():
        return 0
    now = datetime.now().timestamp()
    removed = 0
    for path in base.iterdir():
        if path.is_file() and now - path.stat().st_mtime > ttl_seconds:
            path.unlink(missing_ok=True)
            removed += 1
    return removed

