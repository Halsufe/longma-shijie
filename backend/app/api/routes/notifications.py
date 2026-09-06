import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.errors import AppException
from backend.app.repositories.notification_repo import NotificationRepository
from backend.app.schemas.school import NotificationInfo, NotificationListResponse
from backend.app.api.deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/notifications", response_model=NotificationListResponse)
async def list_notifications(
    is_read: bool = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),  # 上限由 normalize_page_size 静默截断到 100
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items, total = NotificationRepository.list_by_user(
        db, current_user.id, is_read=is_read, page=page, page_size=page_size
    )
    unread = NotificationRepository.count_unread(db, current_user.id)
    return NotificationListResponse(
        total=total,
        items=[NotificationInfo.model_validate(n) for n in items],
        unread_count=unread,
    )


@router.get("/notifications/unread-count")
async def unread_count(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"unread_count": NotificationRepository.count_unread(db, current_user.id)}


@router.put("/notifications/{notification_id}/read")
async def mark_read(
    notification_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ok = NotificationRepository.mark_read(db, notification_id, current_user.id)
    if not ok:
        raise AppException("NOTIFICATION_NOT_FOUND", "通知不存在", 404)
    return {"message": "已标记为已读"}


@router.put("/notifications/read-all")
async def mark_all_read(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = NotificationRepository.mark_all_read(db, current_user.id)
    return {"message": f"已标记 {count} 条为已读"}
