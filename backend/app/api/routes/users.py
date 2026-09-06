from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.errors import AppException
from backend.app.repositories.user_repo import UserRepository
from backend.app.repositories.session_repo import SessionRepository
from backend.app.schemas.user import UserInfo, UserUpdate, AlumniConversionRequestCreate, AlumniConversionRequestInfo
from backend.app.schemas.session import SessionInfo, SessionListResponse, OperationResult
from backend.app.api.deps import get_current_user
from backend.app.services.profile_service import update_profile
from backend.app.services.alumni_conversion_service import AlumniConversionService
from backend.app.models.user import AlumniConversionRequest
from backend.app.repositories.notification_repo import NotificationRepository
from backend.app.repositories.audit_repo import AuditRepository

router = APIRouter()


@router.get("/me", response_model=UserInfo)
async def get_my_info(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return current_user


@router.put("/me", response_model=UserInfo)
async def update_my_info(
    form: UserUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if form.name is not None:
        current_user = UserRepository.update(db, current_user, name=form.name)
    if form.graduation_year is not None:
        current_user = UserRepository.update(db, current_user, graduation_year=form.graduation_year)
    if form.profile is not None:
        try:
            update_profile(current_user, form.profile)
        except ValueError as exc:
            raise AppException("PROFILE_INVALID", str(exc), 400)
        current_user = UserRepository.set_profile(db, current_user, current_user.profile)
    return current_user


@router.post("/me/alumni-request", response_model=AlumniConversionRequestInfo)
async def create_alumni_request(
    form: AlumniConversionRequestCreate, current_user=Depends(get_current_user), db: Session = Depends(get_db)
):
    try:
        item = AlumniConversionService.request(db, current_user, form.graduation_year)
    except ValueError as exc:
        raise AppException("ALUMNI_REQUEST_INVALID", str(exc), 400)
    AuditRepository.create(
        db, current_user.id, current_user.name, "alumni_request.create", "alumni_request", str(item.id)
    )
    admins = UserRepository.list_by_role(db, "admin")
    NotificationRepository.create_for_many(
        db,
        [a.id for a in admins],
        type="system",
        title="新的校友转换申请",
        content="请审核校友转换申请",
        ref_type="alumni_request",
        ref_id=item.id,
    )
    return item


@router.get("/me/alumni-request", response_model=AlumniConversionRequestInfo | None)
async def get_alumni_request(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(AlumniConversionRequest)
        .filter(AlumniConversionRequest.user_id == current_user.id)
        .order_by(AlumniConversionRequest.id.desc())
        .first()
    )


@router.get("/me/sessions", response_model=SessionListResponse)
async def list_my_sessions(
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """当前用户的活跃设备会话列表"""
    sessions = SessionRepository.list_active_by_user(db, current_user.id)
    current_jti = getattr(request.state, "token_jti", None)
    items = []
    for s in sessions:
        items.append(
            SessionInfo(
                id=s.id,
                device_id=s.device_id,
                device_name=s.device_name,
                ip=s.ip,
                user_agent=s.user_agent,
                issued_at=s.issued_at,
                last_active_at=s.last_active_at,
                expires_at=s.expires_at,
                is_current=(s.jti == current_jti),
            )
        )
    return SessionListResponse(total=len(items), items=items)


@router.delete("/me/sessions/{session_id}", response_model=OperationResult)
async def revoke_my_session(
    session_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """撤销指定的设备会话（下线指定设备）"""
    s = SessionRepository.get_by_id(db, session_id, current_user.id)
    if not s:
        raise AppException("SESSION_NOT_FOUND", "会话不存在", 404)
    SessionRepository.revoke(db, s)
    return OperationResult(success=True, message="会话已撤销")
