import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.errors import AppException
from backend.app.models.user import User
from backend.app.models.chat import ChatSession, ChatMessage
from backend.app.models.file import KnowledgeFile
from backend.app.models.skill import Skill, SkillCall
from backend.app.models.school import Assignment, Submission
from backend.app.schemas.audit import SystemStats, StorageUsageInfo
from backend.app.services.storage_service import StorageStatService
from backend.app.api.deps import require_admin
from backend.app.services.admin_platform_service import activity_stats, business_stats
from fastapi.responses import Response
import csv
import io

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/stats", response_model=SystemStats)
async def system_stats(
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """系统统计概览"""
    # 用户
    total_users = db.query(func.count(User.id)).filter(User.deleted_at.is_(None)).scalar() or 0
    admin_count = (
        db.query(func.count(User.id))
        .filter(User.deleted_at.is_(None), User.role == "admin")
        .scalar()
        or 0
    )
    active_users = (
        db.query(func.count(User.id))
        .filter(User.deleted_at.is_(None), User.status == "active")
        .scalar()
        or 0
    )

    # 对话
    session_count = db.query(func.count(ChatSession.id)).scalar() or 0
    message_count = db.query(func.count(ChatMessage.id)).scalar() or 0

    # 知识库
    personal_files = (
        db.query(func.count(KnowledgeFile.id))
        .filter(KnowledgeFile.scope == "personal", KnowledgeFile.deleted_at.is_(None))
        .scalar()
        or 0
    )
    class_files = (
        db.query(func.count(KnowledgeFile.id))
        .filter(KnowledgeFile.scope == "class", KnowledgeFile.deleted_at.is_(None))
        .scalar()
        or 0
    )
    total_size = (
        db.query(func.sum(KnowledgeFile.size))
        .filter(KnowledgeFile.deleted_at.is_(None))
        .scalar()
        or 0
    )

    # Skills
    legacy_skill_count = (
        db.query(func.count(Skill.id)).filter(Skill.category != "business").scalar() or 0
    )
    business_skill_count = (
        db.query(func.count(Skill.id)).filter(Skill.category == "business").scalar() or 0
    )
    skill_call_count = db.query(func.count(SkillCall.id)).scalar() or 0

    # 作业
    assignment_count = (
        db.query(func.count(Assignment.id)).filter(Assignment.deleted_at.is_(None)).scalar() or 0
    )
    submission_count = db.query(func.count(Submission.id)).scalar() or 0

    return SystemStats(
        users={
            "total": total_users,
            "admins": admin_count,
            "active": active_users,
        },
        chat={
            "sessions": session_count,
            "messages": message_count,
        },
        knowledge={
            "personal_files": personal_files,
            "class_files": class_files,
            "total_size_bytes": int(total_size),
        },
        skills={
            # Preserve the original field semantics for existing admin clients.
            "skills": legacy_skill_count,
            "business_skills": business_skill_count,
            "total_skills": legacy_skill_count + business_skill_count,
            "calls": skill_call_count,
        },
        assignments={
            "assignments": assignment_count,
            "submissions": submission_count,
        },
    )


@router.get("/storage", response_model=StorageUsageInfo)
async def storage_usage(
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """存储用量明细（按用户）"""
    return StorageStatService.get_usage(db)


@router.get("/stats/activity")
async def stats_activity(days: int = 30, current_user=Depends(require_admin), db: Session = Depends(get_db)):
    if days < 1 or days > 90:
        raise AppException("INVALID_DAYS", "days 必须在 1-90 之间", 400)
    items = activity_stats(db, days)
    return {"days": days, "items": items, "today_dau": items[-1]["dau"] if items else 0}


@router.get("/stats/activity/export")
async def export_activity(days: int = 30, current_user=Depends(require_admin), db: Session = Depends(get_db)):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["日期", "DAU"])
    writer.writerows((item["date"], item["dau"]) for item in activity_stats(db, days))
    return Response(content=("\ufeff" + output.getvalue()).encode("utf-8"), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=activity.csv"})


@router.get("/stats/business")
async def stats_business(year: int | None = Query(None), class_name: str | None = Query(None), grade: str | None = Query(None), category: str | None = Query(None), current_user=Depends(require_admin), db: Session = Depends(get_db)):
    result = business_stats(db, year=year, category=category)
    result["filters"] = {"year": year, "class_name": class_name, "grade": grade, "category": category}
    return result
