from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from backend.app.core.database import CST, local_now
from backend.app.models.announcement import AnnouncementDigest, AnnouncementDigestDelivery
from backend.app.models.notification import Notification
from backend.app.models.user import User
from backend.app.repositories.announcement_repo import AnnouncementRepository


def digest_window(run_at: datetime | None = None) -> tuple[datetime, datetime]:
    current = (run_at or local_now()).astimezone(CST)
    end = current.replace(hour=20, minute=0, second=0, microsecond=0)
    if current < end:
        end -= timedelta(days=1)
    start = end - timedelta(days=1)
    return start, end


class AnnouncementDigestService:
    @staticmethod
    def build(db: Session, run_at: datetime | None = None, *, is_recovery: bool = False) -> AnnouncementDigest:
        start, end = digest_window(run_at)
        existing = db.query(AnnouncementDigest).filter(AnnouncementDigest.window_start == start, AnnouncementDigest.window_end == end).first()
        if existing:
            return existing
        items, _ = AnnouncementRepository.list_visible(db, page=1, page_size=100, published_from=start.date(), published_to=end.date())
        snapshot = [{"id": item.id, "title": item.title, "date": item.published_at.isoformat(), "summary": item.summary_text} for item in items]
        titles: list[str] = [str(item["title"]) for item in snapshot]
        text = "今日无新通知" if not snapshot else f"今日学校公告 {len(snapshot)} 条：" + "；".join(titles)
        digest = AnnouncementDigest(window_start=start, window_end=end, snapshot_json=json.dumps(snapshot, ensure_ascii=False), notification_text=text, status="ready", is_recovery=is_recovery)
        db.add(digest)
        db.commit()
        db.refresh(digest)
        return digest

    @staticmethod
    def deliver(db: Session, digest: AnnouncementDigest, limit: int = 1000) -> int:
        users = db.query(User).filter(User.deleted_at.is_(None), User.status == "active").limit(limit).all()
        created = 0
        for user in users:
            delivery = db.query(AnnouncementDigestDelivery).filter(AnnouncementDigestDelivery.digest_id == digest.id, AnnouncementDigestDelivery.user_id == user.id).first()
            if delivery and delivery.status == "sent":
                continue
            notification = db.query(Notification).filter(Notification.user_id == user.id, Notification.ref_type == "school_announcement_digest", Notification.ref_id == digest.id).first()
            if not notification:
                notification = Notification(user_id=user.id, type="school_announcement_digest", title="学校公告汇总", content=digest.notification_text, ref_type="school_announcement_digest", ref_id=digest.id)
                db.add(notification)
                db.flush()
                created += 1
            if not delivery:
                delivery = AnnouncementDigestDelivery(digest_id=digest.id, user_id=user.id, status="sent", notification_id=notification.id, sent_at=local_now())
                db.add(delivery)
            else:
                delivery.status = "sent"
                delivery.notification_id = notification.id
                delivery.sent_at = local_now()
        db.commit()
        return created
