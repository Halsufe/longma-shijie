from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy.orm import Session

from backend.app.models.notification import Notification
from backend.app.repositories.notification_repo import NotificationRepository


PARTY_ACTIVITY_NOTICE = "party_activity_notice"
PARTY_ACTIVITY_REMINDER = "party_activity_reminder"
PARTY_STATUS_CHANGE = "party_status_change"
POLITICAL_STATUS_CHANGE = "political_status_change"


class PartyNotifyAdapter:
    """党建业务到现有站内通知中心的幂等适配层。"""

    @staticmethod
    def _create_many_once(
        db: Session,
        *,
        user_ids: Iterable[int],
        notification_type: str,
        title: str,
        content: str,
        ref_type: str,
        ref_id: int,
    ) -> int:
        existing = (
            db.query(Notification.id)
            .filter(
                Notification.type == notification_type,
                Notification.ref_type == ref_type,
                Notification.ref_id == ref_id,
            )
            .first()
        )
        targets = list(dict.fromkeys(user_ids))
        if existing or not targets:
            return 0
        return NotificationRepository.create_for_many(
            db,
            user_ids=targets,
            type=notification_type,
            title=title,
            content=content,
            ref_type=ref_type,
            ref_id=ref_id,
        )

    @staticmethod
    def notify_party_activity_published(
        db: Session,
        *,
        activity=None,
        target_user_ids: Iterable[int],
        activity_id: int | None = None,
        title: str | None = None,
        content: str | None = None,
    ) -> int:
        resolved_id = activity.id if activity is not None else activity_id
        if resolved_id is None:
            raise ValueError("activity_id is required")
        resolved_title = activity.title if activity is not None else (title or "党建活动")
        resolved_content = activity.content if activity is not None else (content or "")
        return PartyNotifyAdapter._create_many_once(
            db,
            user_ids=target_user_ids,
            notification_type=PARTY_ACTIVITY_NOTICE,
            title=f"党建活动：{resolved_title}",
            content=resolved_content,
            ref_type="party_activity",
            ref_id=resolved_id,
        )

    @staticmethod
    def notify_party_activity_reminder(
        db: Session,
        *,
        activity_id: int,
        activity_title: str,
        target_user_ids: Iterable[int],
        content: str,
    ) -> int:
        return PartyNotifyAdapter._create_many_once(
            db,
            user_ids=target_user_ids,
            notification_type=PARTY_ACTIVITY_REMINDER,
            title=f"党建活动提醒：{activity_title}",
            content=content,
            ref_type="party_activity",
            ref_id=activity_id,
        )

    @staticmethod
    def notify_party_status_change(
        db: Session,
        *,
        user_id: int,
        previous_status: str,
        current_status: str,
    ) -> int:
        return PartyNotifyAdapter._create_many_once(
            db,
            user_ids=[user_id],
            notification_type=PARTY_STATUS_CHANGE,
            title="党员发展阶段已更新",
            content=f"您的党员发展阶段已由“{previous_status}”变更为“{current_status}”。",
            ref_type="party_member",
            ref_id=user_id,
        )

    @staticmethod
    def notify_political_status_approved(
        db: Session,
        *,
        review_id: int,
        user_id: int,
        political_status: str,
    ) -> int:
        return PartyNotifyAdapter._create_many_once(
            db,
            user_ids=[user_id],
            notification_type=POLITICAL_STATUS_CHANGE,
            title="政治面貌申请已通过",
            content=f"您的政治面貌已更新为“{political_status}”。",
            ref_type="political_status_review",
            ref_id=review_id,
        )

    @staticmethod
    def notify_party_registration_result(
        db: Session,
        *,
        participant_id: int,
        user_id: int,
        activity_title: str,
        registration_status: str,
    ) -> int:
        registered = registration_status == "registered"
        action = "报名成功" if registered else "已取消报名"
        ref_type = (
            "party_registration_registered"
            if registered
            else "party_registration_cancelled"
        )
        return PartyNotifyAdapter._create_many_once(
            db,
            user_ids=[user_id],
            notification_type=PARTY_ACTIVITY_NOTICE,
            title=f"党建活动{action}",
            content=f"您对活动“{activity_title}”的操作结果：{action}。",
            ref_type=ref_type,
            ref_id=participant_id,
        )

    @staticmethod
    def notify_party_attendance_result(
        db: Session,
        *,
        participant_id: int,
        user_id: int,
        activity_title: str,
        attendance_status: str,
    ) -> int:
        label = "签到成功" if attendance_status == "signed_in" else "已标记缺席"
        return PartyNotifyAdapter._create_many_once(
            db,
            user_ids=[user_id],
            notification_type=PARTY_ACTIVITY_NOTICE,
            title=f"党建活动{label}",
            content=f"活动“{activity_title}”的考勤结果：{label}。",
            ref_type=f"party_attendance_{attendance_status}",
            ref_id=participant_id,
        )


notify_party_activity_published = PartyNotifyAdapter.notify_party_activity_published
notify_party_activity_reminder = PartyNotifyAdapter.notify_party_activity_reminder
notify_party_status_change = PartyNotifyAdapter.notify_party_status_change
notify_political_status_approved = PartyNotifyAdapter.notify_political_status_approved
notify_party_registration_result = PartyNotifyAdapter.notify_party_registration_result
notify_party_attendance_result = PartyNotifyAdapter.notify_party_attendance_result
notify_party_registration = PartyNotifyAdapter.notify_party_registration_result
notify_party_sign_in = PartyNotifyAdapter.notify_party_attendance_result
