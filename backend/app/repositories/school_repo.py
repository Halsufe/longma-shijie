from __future__ import annotations

import builtins
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from backend.app.models.school import (
    Course,
    CourseSchedule,
    Assignment,
    Submission,
    SubmissionVersion,
)
from backend.app.core.pagination import normalize_page, normalize_page_size
from backend.app.core.database import local_now


class CourseRepository:
    @staticmethod
    def create(db: Session, created_by: int, **kwargs) -> Course:
        course = Course(created_by=created_by, **kwargs)
        db.add(course)
        db.commit()
        db.refresh(course)
        return course

    @staticmethod
    def get_by_id(db: Session, course_id: int, include_deleted: bool = False) -> Optional[Course]:
        q = db.query(Course).filter(Course.id == course_id)
        if not include_deleted:
            q = q.filter(Course.deleted_at.is_(None))
        return q.first()

    @staticmethod
    def list(
        db: Session,
        page: int = 1,
        page_size: int = 50,
        q: Optional[str] = None,
        semester: Optional[str] = None,
    ) -> tuple[list[Course], int]:
        page = normalize_page(page)
        page_size = normalize_page_size(page_size)
        query = db.query(Course).filter(Course.deleted_at.is_(None))
        if q:
            query = query.filter(
                or_(
                    Course.name.ilike(f"%{q}%"),
                    Course.teacher.ilike(f"%{q}%"),
                )
            )
        if semester:
            query = query.filter(Course.semester == semester)
        total = query.count()
        items = (
            query.order_by(desc(Course.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    @staticmethod
    def update(db: Session, course: Course, **kwargs) -> Course:
        for k, v in kwargs.items():
            if hasattr(course, k) and v is not None:
                setattr(course, k, v)
        db.commit()
        db.refresh(course)
        return course

    @staticmethod
    def soft_delete(db: Session, course: Course) -> None:
        course.deleted_at = local_now()
        db.commit()


class ScheduleRepository:
    @staticmethod
    def list_by_course(db: Session, course_id: int) -> list[CourseSchedule]:
        return (
            db.query(CourseSchedule)
            .filter(CourseSchedule.course_id == course_id)
            .order_by(CourseSchedule.weekday, CourseSchedule.start_period)
            .all()
        )

    @staticmethod
    def list_by_weekday(db: Session, weekday: int, course_ids: list[int]) -> list[CourseSchedule]:
        if not course_ids:
            return []
        return (
            db.query(CourseSchedule)
            .filter(CourseSchedule.weekday == weekday, CourseSchedule.course_id.in_(course_ids))
            .order_by(CourseSchedule.start_period)
            .all()
        )

    @staticmethod
    def replace_for_course(db: Session, course_id: int, schedules: list[dict]) -> list[CourseSchedule]:
        """覆盖式更新某课程的所有安排"""
        db.query(CourseSchedule).filter(CourseSchedule.course_id == course_id).delete()
        db.flush()
        created = []
        for s in schedules:
            obj = CourseSchedule(course_id=course_id, **s)
            db.add(obj)
            created.append(obj)
        db.commit()
        for obj in created:
            db.refresh(obj)
        return created


class AssignmentRepository:
    @staticmethod
    def create(db: Session, created_by: int, **kwargs) -> Assignment:
        a = Assignment(created_by=created_by, **kwargs)
        db.add(a)
        db.commit()
        db.refresh(a)
        return a

    @staticmethod
    def get_by_id(db: Session, assignment_id: int, include_deleted: bool = False) -> Optional[Assignment]:
        q = db.query(Assignment).filter(Assignment.id == assignment_id)
        if not include_deleted:
            q = q.filter(Assignment.deleted_at.is_(None))
        return q.first()

    @staticmethod
    def list(
        db: Session,
        course_id: Optional[int] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[builtins.list[Assignment], int]:
        page = normalize_page(page)
        page_size = normalize_page_size(page_size)
        query = db.query(Assignment).filter(Assignment.deleted_at.is_(None))
        if course_id:
            query = query.filter(Assignment.course_id == course_id)
        if status:
            query = query.filter(Assignment.status == status)
        total = query.count()
        items = (
            query.order_by(desc(Assignment.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    @staticmethod
    def list_published_for_user(
        db: Session, course_ids: builtins.list[int], page: int = 1, page_size: int = 50
    ) -> tuple[builtins.list[Assignment], int]:
        """用户可见的已发布作业"""
        page = normalize_page(page)
        page_size = normalize_page_size(page_size)
        query = db.query(Assignment).filter(
            Assignment.deleted_at.is_(None), Assignment.status == "published"
        )
        if course_ids:
            query = query.filter(Assignment.course_id.in_(course_ids))
        total = query.count()
        items = (
            query.order_by(desc(Assignment.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    @staticmethod
    def update(db: Session, a: Assignment, **kwargs) -> Assignment:
        for k, v in kwargs.items():
            if hasattr(a, k) and v is not None:
                setattr(a, k, v)
        db.commit()
        db.refresh(a)
        return a

    @staticmethod
    def soft_delete(db: Session, a: Assignment) -> None:
        a.deleted_at = local_now()
        db.commit()


class SubmissionRepository:
    @staticmethod
    def get_or_create(db: Session, assignment_id: int, user_id: int) -> Submission:
        """获取已有提交（最新版本），没有则创建空记录"""
        sub = (
            db.query(Submission)
            .filter(Submission.assignment_id == assignment_id, Submission.user_id == user_id)
            .first()
        )
        if not sub:
            sub = Submission(assignment_id=assignment_id, user_id=user_id, content="")
            db.add(sub)
            db.commit()
            db.refresh(sub)
        return sub

    @staticmethod
    def get_by_assignment_and_user(
        db: Session, assignment_id: int, user_id: int
    ) -> Optional[Submission]:
        return (
            db.query(Submission)
            .filter(Submission.assignment_id == assignment_id, Submission.user_id == user_id)
            .first()
        )

    @staticmethod
    def list_by_assignment(db: Session, assignment_id: int) -> list[Submission]:
        return (
            db.query(Submission)
            .filter(Submission.assignment_id == assignment_id)
            .order_by(desc(Submission.submitted_at))
            .all()
        )

    @staticmethod
    def list_by_user(db: Session, user_id: int) -> list[Submission]:
        return (
            db.query(Submission)
            .filter(Submission.user_id == user_id)
            .order_by(desc(Submission.submitted_at))
            .all()
        )

    @staticmethod
    def add_version(db: Session, submission_id: int, content: str, attachment_name: Optional[str]) -> int:
        """追加一个历史版本，返回版本号"""
        last = (
            db.query(SubmissionVersion)
            .filter(SubmissionVersion.submission_id == submission_id)
            .order_by(desc(SubmissionVersion.version))
            .first()
        )
        version = (last.version + 1) if last else 1
        v = SubmissionVersion(
            submission_id=submission_id,
            content=content,
            attachment_name=attachment_name,
            version=version,
        )
        db.add(v)
        db.commit()
        return version

    @staticmethod
    def list_versions(db: Session, submission_id: int) -> list[SubmissionVersion]:
        return (
            db.query(SubmissionVersion)
            .filter(SubmissionVersion.submission_id == submission_id)
            .order_by(desc(SubmissionVersion.version))
            .all()
        )

    @staticmethod
    def grade(db: Session, sub: Submission, score: int, feedback: Optional[str]) -> Submission:
        sub.score = score
        sub.feedback = feedback
        sub.status = "graded"
        db.commit()
        db.refresh(sub)
        return sub
