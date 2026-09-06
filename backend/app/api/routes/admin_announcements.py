from __future__ import annotations
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from backend.app.api.deps import get_db, require_admin
from backend.app.core.database import local_now
from backend.app.models.announcement import AnnouncementTaskRun
from backend.app.repositories.announcement_repo import AnnouncementRepository

router = APIRouter()

@router.get("/announcement-tasks")
async def list_announcement_tasks(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), current_user=Depends(require_admin), db: Session = Depends(get_db)):
    query = db.query(AnnouncementTaskRun).order_by(AnnouncementTaskRun.created_at.desc())
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [{"id": item.id, "task_key": item.task_key, "task_type": item.task_type, "status": item.status, "error_summary": item.error_summary, "created_at": item.created_at} for item in items]}

@router.post("/announcement-tasks/retry/{task_id}", status_code=status.HTTP_202_ACCEPTED)
async def retry_announcement_task(task_id: int, current_user=Depends(require_admin), db: Session = Depends(get_db)):
    task = db.query(AnnouncementTaskRun).filter(AnnouncementTaskRun.id == task_id).first()
    if not task:
        from backend.app.core.errors import AppException
        raise AppException("TASK_NOT_FOUND", "公告任务不存在", 404)
    retry = AnnouncementTaskRun(task_key=f"manual-retry:{task.id}:{int(local_now().timestamp())}", task_type=task.task_type, retry_of_id=task.id, manual=True)
    db.add(retry)
    db.commit()
    db.refresh(retry)
    return {"task_id": retry.id, "status": retry.status}

@router.get("/announcement-sources/health")
async def announcement_source_health(current_user=Depends(require_admin), db: Session = Depends(get_db)):
    return [{"code": item.code, "name": item.name, "enabled": item.enabled, "last_success_at": item.last_success_at, "consecutive_failures": item.consecutive_failures} for item in AnnouncementRepository.list_sources(db)]

