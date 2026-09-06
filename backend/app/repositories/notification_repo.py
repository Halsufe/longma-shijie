from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.app.models.notification import Notification
from backend.app.core.pagination import normalize_page, normalize_page_size


class NotificationRepository:
    @staticmethod
    def create(
        db: Session,
        user_id: int,
        type: str,
        title: str,
        content: str = "",
        ref_type: Optional[str] = None,
        ref_id: Optional[int] = None,
    ) -> Notification:
        n = Notification(
            user_id=user_id,
            type=type,
            title=title,
            content=content,
            ref_type=ref_type,
            ref_id=ref_id,
        )
        db.add(n)
        db.commit()
        db.refresh(n)
        return n

    @staticmethod
    def list_by_user(
        db: Session,
        user_id: int,
        is_read: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Notification], int]:
        page = normalize_page(page)
        page_size = normalize_page_size(page_size)
        query = db.query(Notification).filter(Notification.user_id == user_id)
        if is_read is not None:
            query = query.filter(Notification.is_read == is_read)
        total = query.count()
        items = (
            query.order_by(desc(Notification.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    @staticmethod
    def count_unread(db: Session, user_id: int) -> int:
        return (
            db.query(Notification)
            .filter(Notification.user_id == user_id, Notification.is_read.is_(False))
            .count()
        )

    @staticmethod
    def mark_read(db: Session, notification_id: int, user_id: int) -> bool:
        n = (
            db.query(Notification)
            .filter(Notification.id == notification_id, Notification.user_id == user_id)
            .first()
        )
        if not n:
            return False
        n.is_read = True
        db.commit()
        return True

    @staticmethod
    def mark_all_read(db: Session, user_id: int) -> int:
        count = (
            db.query(Notification)
            .filter(Notification.user_id == user_id, Notification.is_read.is_(False))
            .update({Notification.is_read: True})
        )
        db.commit()
        return count

    @staticmethod
    def create_for_many(db: Session, user_ids: list[int], **kwargs) -> int:
        """批量给多个用户创建相同通知（用于新作业通知），返回创建数"""
        for uid in user_ids:
            n = Notification(user_id=uid, **kwargs)
            db.add(n)
        db.commit()
        return len(user_ids)
