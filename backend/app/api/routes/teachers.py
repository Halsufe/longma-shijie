from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from backend.app.core.database import get_db
from backend.app.repositories.teacher_repo import TeacherRepository
from backend.app.api.deps import get_current_user, require_teacher_or_admin, require_student_or_alumni
from backend.app.schemas.teacher import (
    DirectionCreate, DirectionUpdate, DirectionInfo, DirectionListResponse,
    TeacherInfo, TeacherListResponse
)

router = APIRouter()


@router.post("/directions", response_model=DirectionInfo)
async def create_direction(
    form: DirectionCreate,
    current_user=Depends(require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    return TeacherRepository.create_direction(db, current_user.id, **form.model_dump(exclude_unset=True))


@router.get("/directions/mine", response_model=DirectionListResponse)
async def list_my_directions(
    current_user=Depends(require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    items = TeacherRepository.list_by_teacher(db, current_user.id, active_only=True)
    return DirectionListResponse(total=len(items), items=[DirectionInfo.model_validate(d) for d in items])


@router.put("/directions/{direction_id}", response_model=DirectionInfo)
async def update_direction(
    direction_id: int,
    form: DirectionUpdate,
    current_user=Depends(require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    from backend.app.core.errors import AppException
    d = TeacherRepository.get_direction(db, direction_id)
    if not d:
        raise AppException("NOT_FOUND", "方向不存在", 404)
    if d.teacher_id != current_user.id and not current_user.is_admin:
        raise AppException("FORBIDDEN", "无权修改", 403)
    return TeacherRepository.update_direction(db, d, **form.model_dump(exclude_unset=True))


@router.delete("/directions/{direction_id}")
async def delete_direction(
    direction_id: int,
    current_user=Depends(require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    from backend.app.core.errors import AppException
    d = TeacherRepository.get_direction(db, direction_id)
    if not d:
        raise AppException("NOT_FOUND", "方向不存在", 404)
    if d.teacher_id != current_user.id and not current_user.is_admin:
        raise AppException("FORBIDDEN", "无权删除", 403)
    TeacherRepository.soft_delete_direction(db, d)
    return {"success": True}


@router.get("/match", response_model=TeacherListResponse)
async def match_teachers(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    q: Optional[str] = None,
    tag: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
):
    items, total = TeacherRepository.match_teachers(db, q=q, tag=tag, page=page, page_size=page_size)
    return TeacherListResponse(total=total, items=[TeacherInfo.model_validate(t) for t in items])


@router.get("/{teacher_id}", response_model=TeacherInfo)
async def get_teacher(
    teacher_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from backend.app.core.errors import AppException
    t = TeacherRepository.get_teacher(db, teacher_id)
    if not t:
        raise AppException("NOT_FOUND", "教师不存在", 404)
    return t