from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.app.models.achievement import Achievement
from backend.app.models.notification import Notification
from backend.app.models.resource import Resource
from backend.app.models.school import Assignment, Course, CourseSchedule
from backend.app.models.user import User
from backend.app.repositories.user_repo import UserRepository
from backend.app.services.party_activity_service import PartyActivityService


class SystemSearchService:
    """Read-only, permission-aware context from core platform modules."""

    INTENTS = {
        "courses": ("课程", "课表", "上课", "教室", "老师", "教师"),
        "assignments": ("作业", "截止", "提交", "分数", "成绩"),
        "resources": ("资源", "竞赛", "比赛", "招募", "工具", "经验"),
        "achievements": ("成果", "获奖", "论文", "专利", "科研"),
        "notifications": ("通知", "消息", "提醒"),
        "party": ("党建", "党日", "团日", "政治学习", "活动"),
        "users": ("用户", "学生", "校友", "账号"),
    }

    @classmethod
    def _matches(cls, query: str, intent: str) -> bool:
        return any(keyword in query for keyword in cls.INTENTS[intent])

    @staticmethod
    def _item(name: str, content: str, source_type: str) -> dict[str, str]:
        return {"name": name, "content": content[:1600], "source_type": source_type}

    @classmethod
    def search(cls, db: Session, query: str, user_id: int, limit: int = 12) -> list[dict[str, str]]:
        user = UserRepository.get_by_id(db, user_id)
        if user is None:
            return []
        items: list[dict[str, str]] = []

        if cls._matches(query, "courses"):
            courses = db.query(Course).filter(Course.deleted_at.is_(None)).order_by(Course.id.desc()).limit(8).all()
            course_ids = [course.id for course in courses]
            schedules = db.query(CourseSchedule).filter(CourseSchedule.course_id.in_(course_ids)).all() if course_ids else []
            by_course: dict[int, list[CourseSchedule]] = {}
            for schedule in schedules:
                by_course.setdefault(schedule.course_id, []).append(schedule)
            for course in courses:
                schedule_text = "；".join(
                    f"周{row.weekday} 第{row.start_period}-{row.end_period}节 {row.location or ''}".strip()
                    for row in by_course.get(course.id, [])
                )
                items.append(cls._item(
                    f"课程：{course.name}",
                    f"教师：{course.teacher or '未设置'}；学期：{course.semester or '未设置'}；安排：{schedule_text or '未设置'}；说明：{course.description or '无'}",
                    "course",
                ))

        if cls._matches(query, "assignments"):
            assignment_query = db.query(Assignment).filter(Assignment.deleted_at.is_(None))
            if not user.is_admin and not user.is_teacher:
                assignment_query = assignment_query.filter(Assignment.status == "published")
            for assignment in assignment_query.order_by(Assignment.id.desc()).limit(8).all():
                items.append(cls._item(
                    f"作业：{assignment.title}",
                    f"状态：{assignment.status}；截止：{assignment.due_at or '未设置'}；说明：{assignment.description or '无'}",
                    "assignment",
                ))

        if cls._matches(query, "resources"):
            for resource in db.query(Resource).filter(
                Resource.status == "approved", Resource.deleted_at.is_(None)
            ).order_by(Resource.id.desc()).limit(8).all():
                items.append(cls._item(
                    f"资源：{resource.title}",
                    f"类型：{resource.type}；来源：{resource.source or '平台用户'}；截止：{resource.deadline or '未设置'}；内容：{resource.content or '无'}",
                    "resource",
                ))

        if cls._matches(query, "achievements"):
            achievement_query = db.query(Achievement).filter(Achievement.deleted_at.is_(None))
            if not user.is_admin:
                achievement_query = achievement_query.filter(Achievement.user_id == user.id)
            for achievement in achievement_query.order_by(Achievement.id.desc()).limit(8).all():
                items.append(cls._item(
                    f"成果：{achievement.title}",
                    f"类别：{achievement.category}；状态：{achievement.status}；日期：{achievement.achievement_date or '未设置'}；说明：{achievement.description or '无'}",
                    "achievement",
                ))

        if cls._matches(query, "notifications"):
            for notification in db.query(Notification).filter(
                Notification.user_id == user.id
            ).order_by(Notification.id.desc()).limit(8).all():
                items.append(cls._item(
                    f"通知：{notification.title}",
                    f"类型：{notification.type}；已读：{'是' if notification.is_read else '否'}；内容：{notification.content}",
                    "notification",
                ))

        if cls._matches(query, "party"):
            activities, _, _, _ = PartyActivityService.list_visible(
                db,
                user,
                status=None,
                category=None,
                year=None,
                page=1,
                page_size=20,
            )
            for activity in activities[:8]:
                items.append(cls._item(
                    f"党建活动：{activity.title}",
                    f"类别：{activity.category}；状态：{activity.status}；时间：{activity.start_at}；地点：{activity.location}；内容：{activity.content}",
                    "party_activity",
                ))

        if cls._matches(query, "users") and user.is_admin:
            for account in db.query(User).filter(User.deleted_at.is_(None)).order_by(User.id.desc()).limit(8).all():
                items.append(cls._item(
                    f"用户：{account.name}",
                    f"学号/工号：{account.student_no}；角色：{account.role}；状态：{account.status}",
                    "user",
                ))

        return items[:limit]

    @staticmethod
    def build_context(items: list[dict[str, str]]) -> str:
        return "\n\n".join(
            f"[系统{index}] {item['name']}\n{item['content']}"
            for index, item in enumerate(items, 1)
        )

    @staticmethod
    def citations(items: list[dict[str, str]]) -> list[dict[str, Any]]:
        return [
            {
                "name": item["name"],
                "preview": item["content"][:200],
                "source_type": item["source_type"],
            }
            for item in items
        ]
