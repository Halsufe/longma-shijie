import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.app.repositories.school_repo import (
    AssignmentRepository,
    SubmissionRepository,
)
from backend.app.repositories.notification_repo import NotificationRepository
from backend.app.core.errors import AppException
from backend.app.core.database import local_now

logger = logging.getLogger(__name__)


class SubmissionService:
    """作业提交 + 版本管理"""

    @staticmethod
    def submit(
        db: Session,
        assignment_id: int,
        user_id: int,
        content: str,
        attachment_name: str | None = None,
    ) -> dict:
        """
        提交作业（截止前可更新，保留历史版本）
        返回: {submission_id, version, is_update}
        """
        assignment = AssignmentRepository.get_by_id(db, assignment_id)
        if not assignment:
            raise AppException("ASSIGNMENT_NOT_FOUND", "作业不存在", 404)
        if assignment.status != "published":
            raise AppException("ASSIGNMENT_NOT_PUBLISHED", "作业未发布", 400)

        # 截止时间校验（允许逾期提交但标记）
        is_overdue = False
        now = local_now()
        if assignment.due_at and now > assignment.due_at:
            is_overdue = True
            logger.info("Overdue submission: assignment=%s user=%s", assignment_id, user_id)

        # 获取或创建提交记录
        existing = SubmissionRepository.get_by_assignment_and_user(db, assignment_id, user_id)
        is_update = existing is not None
        sub = SubmissionRepository.get_or_create(db, assignment_id, user_id)

        # 更新最新内容
        sub.content = content
        if attachment_name is not None:
            sub.attachment_name = attachment_name
        sub.submitted_at = now
        # 若已评分，更新提交不清除成绩（教师可重新评）
        db.commit()
        db.refresh(sub)

        # 追加历史版本
        version = SubmissionRepository.add_version(db, sub.id, content, attachment_name)

        logger.info(
            "Submission: assignment=%s user=%s version=%s overdue=%s",
            assignment_id, user_id, version, is_overdue,
        )
        return {
            "submission_id": sub.id,
            "version": version,
            "is_update": is_update,
            "is_overdue": is_overdue,
        }

    @staticmethod
    def grade(
        db: Session,
        submission_id: int,
        score: int,
        feedback: str | None = None,
    ) -> dict:
        """教师评分"""
        from backend.app.models.school import Submission

        sub = db.query(Submission).filter(Submission.id == submission_id).first()
        if not sub:
            raise AppException("SUBMISSION_NOT_FOUND", "提交不存在", 404)

        sub = SubmissionRepository.grade(db, sub, score, feedback)

        # 通知学生
        NotificationRepository.create(
            db,
            user_id=sub.user_id,
            type="assignment",
            title="作业已评分",
            content=f"你的作业获得 {score} 分" + (f"，反馈：{feedback}" if feedback else ""),
            ref_type="submission",
            ref_id=sub.id,
        )
        return {"submission_id": sub.id, "score": score, "status": sub.status}

    @staticmethod
    def get_versions(db: Session, submission_id: int, user_id: int, is_admin: bool) -> list:
        """获取提交历史版本（学生只能看自己的）"""
        from backend.app.models.school import Submission

        sub = db.query(Submission).filter(Submission.id == submission_id).first()
        if not sub:
            raise AppException("SUBMISSION_NOT_FOUND", "提交不存在", 404)
        if not is_admin and sub.user_id != user_id:
            raise AppException("FORBIDDEN", "无权查看他人提交", 403)
        return SubmissionRepository.list_versions(db, submission_id)
