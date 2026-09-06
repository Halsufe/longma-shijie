import logging

from sqlalchemy.orm import Session

from backend.app.repositories.notification_repo import NotificationRepository
from backend.app.repositories.user_repo import UserRepository

logger = logging.getLogger(__name__)


class NotificationService:
    """通知服务：新作业通知（幂等）"""

    @staticmethod
    def notify_new_assignment(
        db: Session,
        assignment_id: int,
        title: str,
        course_name: str = "",
    ) -> int:
        """
        新作业发布时通知所有学生（幂等：已存在同 ref 的通知则跳过）
        返回实际创建通知数
        """
        from backend.app.models.notification import Notification
        from backend.app.models.school import Assignment

        # 幂等检查：已有任一用户收到该作业通知则不再发
        existing = (
            db.query(Notification)
            .filter(
                Notification.ref_type == "assignment",
                Notification.ref_id == assignment_id,
            )
            .first()
        )
        if existing:
            logger.info("Assignment notification already sent: assignment=%s", assignment_id)
            return 0

        # 通知所有启用中的学生
        students = UserRepository.list_active_students(db)
        if not students:
            return 0

        course_info = f"[{course_name}] " if course_name else ""
        created = NotificationRepository.create_for_many(
            db,
            user_ids=[s.id for s in students],
            type="assignment",
            title=f"{course_info}新作业：{title}",
            content=f"课程 {course_name} 发布了新作业「{title}」，请及时查看并提交。",
            ref_type="assignment",
            ref_id=assignment_id,
        )
        logger.info("Notified %d students for assignment=%s", created, assignment_id)
        return created

    @staticmethod
    def notify_due_reminder(
        db: Session,
        assignment_id: int,
        title: str,
        due_at,
        hours_before: int = 24,
    ) -> int:
        """
        截止前提醒（幂等：用 type=reminder + ref 区分不同 hours 档位）
        """
        from backend.app.models.notification import Notification

        reminder_type = f"reminder_{hours_before}h"
        existing = (
            db.query(Notification)
            .filter(
                Notification.type == reminder_type,
                Notification.ref_id == assignment_id,
            )
            .first()
        )
        if existing:
            return 0

        # 仅通知未提交的学生
        from backend.app.models.school import Submission, Assignment

        submitted_ids = (
            db.query(Submission.user_id)
            .filter(Submission.assignment_id == assignment_id)
            .all()
        )
        submitted_set = {uid for (uid,) in submitted_ids}
        students = UserRepository.list_active_students(db)
        targets = [s.id for s in students if s.id not in submitted_set]
        if not targets:
            return 0

        created = NotificationRepository.create_for_many(
            db,
            user_ids=targets,
            type=reminder_type,
            title=f"作业即将截止：{title}",
            content=f"作业「{title}」将于 {due_at.strftime('%m-%d %H:%M')} 截止，请尽快提交。",
            ref_type="assignment",
            ref_id=assignment_id,
        )
        return created
