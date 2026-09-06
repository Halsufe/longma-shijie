"""Standalone announcement worker entry point.

The scheduler is intentionally kept outside FastAPI; deployments can invoke
``python -m backend.app.workers.announcement_worker`` in a separate process.
"""
from __future__ import annotations

import argparse

from backend.app.core.database import SessionLocal
from backend.app.services.announcement_digest_service import AnnouncementDigestService
from backend.app.workers.announcement_cleanup import cleanup_announcements


def run_once() -> dict:
    db = SessionLocal()
    try:
        digest = AnnouncementDigestService.build(db)
        delivered = AnnouncementDigestService.deliver(db, digest)
        cleanup = cleanup_announcements(db)
        return {"digest_id": digest.id, "delivered": delivered, "cleanup": cleanup}
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="run one digest and cleanup cycle")
    parser.parse_args()
    print(run_once())


if __name__ == "__main__":
    main()
