import csv
import io
import logging

from fastapi import APIRouter, Depends, Query, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import hash_password
from backend.app.core.errors import AppException
from backend.app.repositories.user_repo import UserRepository
from backend.app.schemas.user import (
    UserInfo,
    UserCreate,
    UserResetPassword,
    UserListResponse,
    OperationResult,
    AlumniConversionRequestCreate,
    AlumniConversionRequestInfo,
    AlumniReview,
)
from backend.app.api.deps import require_admin
from backend.app.services.alumni_conversion_service import AlumniConversionService
from backend.app.models.user import AlumniConversionRequest
from backend.app.repositories.notification_repo import NotificationRepository
from backend.app.repositories.audit_repo import AuditRepository
from backend.app.services.admin_platform_service import parse_import, import_token, confirm_import, export_users

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/users/{user_id}/convert-alumni", response_model=UserInfo)
async def convert_user_alumni(
    user_id: int,
    form: AlumniConversionRequestCreate,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = UserRepository.get_by_id(db, user_id)
    if not user:
        raise AppException("USER_NOT_FOUND", "用户不存在", 404)
    try:
        user = AlumniConversionService.convert(db, user, form.graduation_year, current_user.id)
    except ValueError as exc:
        raise AppException("ALUMNI_CONVERT_INVALID", str(exc), 400)
    return user


@router.get("/users/alumni-requests", response_model=list[AlumniConversionRequestInfo])
async def list_alumni_requests(
    status: str | None = None, current_user=Depends(require_admin), db: Session = Depends(get_db)
):
    query = db.query(AlumniConversionRequest)
    if status:
        query = query.filter(AlumniConversionRequest.status == status)
    return query.order_by(AlumniConversionRequest.id.desc()).all()


@router.post("/users/alumni-requests/{request_id}/approve", response_model=UserInfo)
async def approve_alumni_request(request_id: int, current_user=Depends(require_admin), db: Session = Depends(get_db)):
    item = db.query(AlumniConversionRequest).filter(AlumniConversionRequest.id == request_id).first()
    if not item:
        raise AppException("REQUEST_NOT_FOUND", "申请不存在", 404)
    try:
        user = AlumniConversionService.review(db, item, current_user, True)
    except ValueError as exc:
        raise AppException("ALUMNI_REVIEW_INVALID", str(exc), 400)
    AuditRepository.create(
        db, current_user.id, current_user.name, "alumni_request.approve", "alumni_request", str(request_id)
    )
    NotificationRepository.create(
        db, user.id, "system", "校友转换已通过", "你的校友转换申请已通过", "alumni_request", request_id
    )
    return user


@router.post("/users/alumni-requests/{request_id}/reject", response_model=UserInfo)
async def reject_alumni_request(
    request_id: int, form: AlumniReview, current_user=Depends(require_admin), db: Session = Depends(get_db)
):
    if not form.comment:
        raise AppException("REJECT_REASON_REQUIRED", "驳回原因必填", 400)
    item = db.query(AlumniConversionRequest).filter(AlumniConversionRequest.id == request_id).first()
    if not item:
        raise AppException("REQUEST_NOT_FOUND", "申请不存在", 404)
    try:
        user = AlumniConversionService.review(db, item, current_user, False, form.comment)
    except ValueError as exc:
        raise AppException("ALUMNI_REVIEW_INVALID", str(exc), 400)
    AuditRepository.create(
        db, current_user.id, current_user.name, "alumni_request.reject", "alumni_request", str(request_id)
    )
    NotificationRepository.create(
        db, user.id, "system", "校友转换申请已驳回", form.comment, "alumni_request", request_id
    )
    return user


# 统一初始密码：新建用户和重置密码均使用此值
DEFAULT_INITIAL_PASSWORD = "123456"


@router.get("/users", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),  # 上限由 normalize_page_size 静默截断到 100
    q: str = Query(None, description="学号或姓名搜索"),
    role: str = Query(None, description="角色筛选"),
    status: str = Query(None, description="状态筛选"),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    items, total = UserRepository.list(db, page=page, page_size=page_size, q=q, role=role, status=status)
    return UserListResponse(total=total, items=[UserInfo.model_validate(u) for u in items])


@router.post("/users", response_model=UserInfo)
async def create_user(
    form: UserCreate,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    existing = UserRepository.get_by_student_no(db, form.student_no)
    if existing:
        raise AppException("STUDENT_NO_EXISTS", f"学号 {form.student_no} 已存在", 400)

    user = UserRepository.create(
        db,
        student_no=form.student_no,
        name=form.name,
        password_hash=hash_password(DEFAULT_INITIAL_PASSWORD),
        role=form.role,
        status="pending_change",
    )
    logger.info("Admin created user: user_id=%s", user.id)
    return UserInfo.model_validate(user)


@router.put("/users/{user_id}", response_model=UserInfo)
async def update_user(
    user_id: int,
    form: UserCreate,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = UserRepository.get_by_id(db, user_id)
    if not user:
        raise AppException("USER_NOT_FOUND", "用户不存在", 404)

    if form.student_no != user.student_no:
        existing = UserRepository.get_by_student_no(db, form.student_no)
        if existing:
            raise AppException("STUDENT_NO_EXISTS", f"学号 {form.student_no} 已存在", 400)

    user = UserRepository.update(db, user, student_no=form.student_no, name=form.name, role=form.role)
    return UserInfo.model_validate(user)


@router.put("/users/{user_id}/reset-password", response_model=OperationResult)
async def reset_user_password(
    user_id: int,
    form: UserResetPassword,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = UserRepository.get_by_id(db, user_id)
    if not user:
        raise AppException("USER_NOT_FOUND", "用户不存在", 404)

    new_password = form.new_password or DEFAULT_INITIAL_PASSWORD
    UserRepository.update(
        db,
        user,
        password_hash=hash_password(new_password),
        status="pending_change",
    )
    logger.info("Admin reset password: user_id=%s", user_id)
    return OperationResult(success=True, message=f"密码已重置为: {new_password}，用户需首次登录修改")


@router.put("/users/{user_id}/enable", response_model=OperationResult)
async def enable_user(
    user_id: int,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = UserRepository.get_by_id(db, user_id)
    if not user:
        raise AppException("USER_NOT_FOUND", "用户不存在", 404)
    UserRepository.update(db, user, status="active")
    return OperationResult(success=True, message="用户已启用")


@router.put("/users/{user_id}/disable", response_model=OperationResult)
async def disable_user(
    user_id: int,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = UserRepository.get_by_id(db, user_id)
    if not user:
        raise AppException("USER_NOT_FOUND", "用户不存在", 404)
    UserRepository.update(db, user, status="disabled")
    return OperationResult(success=True, message="用户已禁用")


@router.delete("/users/{user_id}", response_model=OperationResult)
async def delete_user(
    user_id: int,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    if user_id == current_user.id:
        raise AppException("CANNOT_DELETE_SELF", "不能删除自己的账号", 400)

    user = UserRepository.get_by_id(db, user_id)
    if not user:
        raise AppException("USER_NOT_FOUND", "用户不存在", 404)

    UserRepository.soft_delete(db, user)
    logger.info("Admin deleted user: user_id=%s", user_id)
    return OperationResult(success=True, message="用户已删除")


@router.post("/users/import", response_model=OperationResult)
async def import_users(
    file: UploadFile = File(...),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    if not file.filename or not (file.filename.endswith(".csv") or file.filename.endswith(".xlsx")):
        raise AppException("INVALID_FILE_TYPE", "仅支持 CSV 文件", 400)

    content = await file.read()
    if not content:
        raise AppException("EMPTY_FILE", "文件为空", 400)

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("gbk")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "学号" not in reader.fieldnames:
        raise AppException("INVALID_FORMAT", "CSV 必须包含 '学号' 列", 400)

    summary = {"created": 0, "updated": 0, "skipped": 0, "errors": 0}
    errors_detail = []

    for i, row in enumerate(reader, start=2):
        student_no = (row.get("学号") or row.get("student_no") or "").strip()
        name = (row.get("姓名") or row.get("name") or "").strip()
        role = (row.get("角色") or row.get("role") or "student").strip()
        if role not in ("student", "alumni", "teacher", "admin"):
            role = "student"

        if not student_no or not name:
            summary["errors"] += 1
            errors_detail.append(f"第{i}行: 学号或姓名为空")
            continue

        existing = UserRepository.get_by_student_no(db, student_no)
        if existing:
            if existing.deleted_at is not None:
                UserRepository.restore(db, existing)
                UserRepository.update(db, existing, name=name, role=role)
                summary["updated"] += 1
            else:
                UserRepository.update(db, existing, name=name, role=role)
                summary["updated"] += 1
        else:
            UserRepository.create(
                db,
                student_no=student_no,
                name=name,
                password_hash=hash_password(DEFAULT_INITIAL_PASSWORD),
                role=role,
                status="pending_change",
            )
            summary["created"] += 1

    msg = f"导入完成: 新增 {summary['created']}，更新 {summary['updated']}，跳过 {summary['skipped']}，错误 {summary['errors']}"
    if errors_detail:
        msg += "。错误详情: " + "; ".join(errors_detail[:5])
    logger.info("Import users: %s", msg)
    return OperationResult(success=True, message=msg)


@router.post("/users/import/preview")
async def preview_users_import(file: UploadFile = File(...), current_user=Depends(require_admin), db: Session = Depends(get_db)):
    content = await file.read()
    try:
        parsed = parse_import(content, db)
    except ValueError as exc:
        raise AppException("IMPORT_INVALID", str(exc), 400)
    return {**parsed, "confirmation_token": import_token(content, parsed)}


@router.post("/users/import/confirm")
async def confirm_users_import(file: UploadFile = File(...), confirmation_token: str = Query(...), current_user=Depends(require_admin), db: Session = Depends(get_db)):
    content = await file.read()
    try:
        result = confirm_import(db, content, confirmation_token)
    except ValueError as exc:
        raise AppException("IMPORT_CONFIRM_INVALID", str(exc), 400)
    AuditRepository.create(db, current_user.id, current_user.name, "admin.users.import.confirm", "user", None, detail=result)
    return result


@router.get("/users/export")
async def export_users_csv(q: str | None = Query(None), role: str | None = Query(None), status: str | None = Query(None), current_user=Depends(require_admin), db: Session = Depends(get_db)):
    data = export_users(db, q, role, status)
    AuditRepository.create(db, current_user.id, current_user.name, "admin.users.export", "user", None)
    return Response(content=data, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=users.csv"})
