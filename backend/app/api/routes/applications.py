from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from backend.app.core.database import get_db
from backend.app.repositories.teacher_repo import TeacherRepository
from backend.app.api.deps import get_current_user, require_teacher_or_admin, require_student_or_alumni
from backend.app.schemas.teacher import (
    ApplicationCreate, ApplicationInfo, ApplicationListResponse,
    PlanCreate, PlanUpdate, PlanInfo, PlanListResponse
)

router = APIRouter()


@router.post("", response_model=ApplicationInfo)
async def create_application(
    form: ApplicationCreate,
    current_user=Depends(require_student_or_alumni),
    db: Session = Depends(get_db),
):
    return TeacherRepository.create_application(db, current_user.id, **form.model_dump(exclude_unset=True))


@router.get("/mine/sent", response_model=ApplicationListResponse)
async def list_my_applications(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    status: Optional[str] = None,
):
    items, total = TeacherRepository.list_applications_by_student(db, current_user.id, page, page_size, status)
    return ApplicationListResponse(total=total, items=[ApplicationInfo.model_validate(a) for a in items])


@router.get("/mine/received", response_model=ApplicationListResponse)
async def list_received_applications(
    current_user=Depends(require_teacher_or_admin),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    status: Optional[str] = None,
):
    items, total = TeacherRepository.list_applications_by_teacher(db, current_user.id, page, page_size, status)
    return ApplicationListResponse(total=total, items=[ApplicationInfo.model_validate(a) for a in items])


@router.put("/{app_id}/accept", response_model=ApplicationInfo)
async def accept_application(
    app_id: int,
    current_user=Depends(require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    from backend.app.core.errors import AppException
    a = TeacherRepository.get_application(db, app_id)
    if not a or a.teacher_id != current_user.id:
        raise AppException("NOT_FOUND", "申请不存在", 404)
    return TeacherRepository.update_application_status(db, a, "accepted")


@router.put("/{app_id}/reject", response_model=ApplicationInfo)
async def reject_application(
    app_id: int,
    current_user=Depends(require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    from backend.app.core.errors import AppException
    a = TeacherRepository.get_application(db, app_id)
    if not a or a.teacher_id != current_user.id:
        raise AppException("NOT_FOUND", "申请不存在", 404)
    return TeacherRepository.update_application_status(db, a, "rejected")


@router.delete("/{app_id}")
async def cancel_application(
    app_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from backend.app.core.errors import AppException
    a = TeacherRepository.get_application(db, app_id)
    if not a or a.student_id != current_user.id:
        raise AppException("NOT_FOUND", "申请不存在", 404)
    TeacherRepository.soft_delete_application(db, a)
    return {"success": True}


@router.post("/plans", response_model=PlanInfo)
async def create_plan(
    form: PlanCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return TeacherRepository.create_plan(db, current_user.id, **form.model_dump(exclude_unset=True))


@router.get("/plans/mine", response_model=PlanListResponse)
async def list_my_plans(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    is_completed: Optional[bool] = None,
):
    items, total = TeacherRepository.list_plans(db, current_user.id, page, page_size, is_completed)
    return PlanListResponse(total=total, items=[PlanInfo.model_validate(p) for p in items])


@router.put("/plans/{plan_id}", response_model=PlanInfo)
async def update_plan(
    plan_id: int,
    form: PlanUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from backend.app.core.errors import AppException
    p = TeacherRepository.get_plan(db, plan_id)
    if not p or p.user_id != current_user.id:
        raise AppException("NOT_FOUND", "计划不存在", 404)
    return TeacherRepository.update_plan(db, p, **form.model_dump(exclude_unset=True))


@router.delete("/plans/{plan_id}")
async def delete_plan(
    plan_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from backend.app.core.errors import AppException
    p = TeacherRepository.get_plan(db, plan_id)
    if not p or p.user_id != current_user.id:
        raise AppException("NOT_FOUND", "计划不存在", 404)
    TeacherRepository.soft_delete_plan(db, p)
    return {"success": True}