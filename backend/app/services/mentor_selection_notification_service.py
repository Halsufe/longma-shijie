from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models.mentor_selection import MentorSelectionNotificationDelivery
from backend.app.models.notification import Notification


class MentorSelectionNotificationService:
    """Persisted notification deduplication for worker retries."""

    @staticmethod
    def send_once(
        db: Session,
        *,
        batch_id: int,
        round_name: str,
        event_key: str,
        user_id: int,
        title: str,
        content: str,
    ) -> Notification:
        existing = db.query(MentorSelectionNotificationDelivery).filter_by(
            batch_id=batch_id,
            round=round_name,
            event_key=event_key,
            user_id=user_id,
        ).first()
        if existing and existing.notification_id:
            return db.query(Notification).filter_by(id=existing.notification_id).one()
        notification = Notification(
            user_id=user_id,
            type="mentor_selection",
            title=title,
            content=content,
            ref_type="mentor_selection",
            ref_id=batch_id,
        )
        delivery = MentorSelectionNotificationDelivery(
            batch_id=batch_id,
            round=round_name,
            event_key=event_key,
            user_id=user_id,
        )
        try:
            db.add(notification)
            db.flush()
            delivery.notification_id = notification.id
            db.add(delivery)
            db.commit()
            db.refresh(notification)
            return notification
        except IntegrityError:
            db.rollback()
            delivery = db.query(MentorSelectionNotificationDelivery).filter_by(
                batch_id=batch_id,
                round=round_name,
                event_key=event_key,
                user_id=user_id,
            ).one()
            return db.query(Notification).filter_by(id=delivery.notification_id).one()
