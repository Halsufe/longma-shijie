import mimetypes
import os
import hashlib

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional

from backend.app.core.database import get_db
from backend.app.core.errors import AppException
from backend.app.repositories.achievement_repo import AchievementRepository
from backend.app.models.achievement import Achievement, AchievementStatus
from backend.app.api.deps import get_current_user, require_admin
from backend.app.schemas.achievement import (
    AchievementAdminListItem,
    AchievementAdminListResponse,
    AchievementCreate,
    AchievementUpdate,
    AchievementInfo,
    AchievementListResponse,
)
from backend.app.schemas.user import OperationResult
from backend.app.services.achievement_service import (
    AchievementValidationError,
    derive_validated_date,
    validate_category,
    validate_details,
    validate_level,
)
from backend.app.services.achievement_files import AchievementFileService
from backend.app.services.achievement_templates import ACHIEVEMENT_TEMPLATES
from backend.app.core.confirmation import require_confirmation_token
from backend.app.repositories.audit_repo import AuditRepository

router = APIRouter()


def _raise_validation_error(exc: AchievementValidationError) -> None:
    raise AppException("ACHIEVEMENT_VALIDATION_ERROR", str(exc), 422) from exc


def _normalize_related_lists(payload: dict) -> None:
    for field in ("member_ids", "proofs"):
        if field in payload and payload[field] is None:
            payload[field] = []


def _prepare_proofs(
    payload: dict,
    user_id: int,
    *,
    require_proof: bool,
    fallback_proofs: list[dict] | None = None,
) -> None:
    supplied = "proofs" in payload
    proofs = payload.get("proofs") if supplied else fallback_proofs
    try:
        normalized = AchievementFileService.normalize_proofs(proofs)
        if require_proof and not normalized:
            raise ValueError("新模板成果至少需要上传 1 份证明材料")
        if supplied:
            AchievementFileService.validate_owned(user_id, normalized)
            payload["proofs"] = normalized
    except ValueError as exc:
        raise AppException("ACHIEVEMENT_PROOF_ERROR", str(exc), 422) from exc


def _prepare_create_payload(form: AchievementCreate, user_id: int) -> dict:
    payload = form.model_dump(exclude_unset=True, exclude={"confirmation_token"})
    _normalize_related_lists(payload)
    try:
        validate_category(form.category)
        if "details" in form.model_fields_set:
            details = validate_details(form.category, form.details)
            payload["details"] = details
            payload["level"] = validate_level(form.category, form.level)
            payload["achievement_date"] = derive_validated_date(form.category, details)
    except AchievementValidationError as exc:
        _raise_validation_error(exc)
    _prepare_proofs(
        payload,
        user_id,
        require_proof="details" in form.model_fields_set,
    )
    return payload


def _prepare_update_payload(achievement, form: AchievementUpdate, user_id: int) -> dict:
    payload = form.model_dump(exclude_unset=True, exclude={"confirmation_token"})
    _normalize_related_lists(payload)
    category = payload.get("category", achievement.category)
    details_supplied = "details" in form.model_fields_set
    template_mode = details_supplied or bool(achievement.details)

    try:
        validate_category(category)
        if template_mode:
            details = validate_details(
                category,
                form.details if details_supplied else achievement.details,
            )
            payload["details"] = details
            payload["level"] = validate_level(category, payload.get("level", achievement.level))
            payload["achievement_date"] = derive_validated_date(category, details)
    except AchievementValidationError as exc:
        _raise_validation_error(exc)
    _prepare_proofs(
        payload,
        user_id,
        require_proof=template_mode,
        fallback_proofs=achievement.proofs,
    )
    return payload


def _find_proof_reference(
    db: Session,
    file_id: str,
    *,
    user_id: int | None = None,
) -> tuple[int, dict] | None:
    query = db.query(Achievement).filter(Achievement.deleted_at.is_(None))
    if user_id is not None:
        query = query.filter(Achievement.user_id == user_id)
    for achievement in query.all():
        for proof in achievement.proofs:
            stored_name = str(proof.get("stored_name") or proof.get("path") or proof.get("id") or "")
            if os.path.basename(stored_name) == file_id:
                return achievement.user_id, proof
    return None


def _remaining_user_proofs(db: Session, user_id: int) -> list[dict]:
    achievements = db.query(Achievement).filter(
        Achievement.user_id == user_id,
        Achievement.deleted_at.is_(None),
    ).all()
    return [proof for achievement in achievements for proof in achievement.proofs]


def _admin_list_item(achievement: Achievement) -> AchievementAdminListItem:
    template = ACHIEVEMENT_TEMPLATES.get(achievement.category)
    details = achievement.details
    summary_keys = [field.key for field in template.fields[:4]] if template else list(details)[:4]
    achievement_date = achievement.achievement_date or ""
    year = int(achievement_date[:4]) if achievement_date[:4].isdigit() else None
    return AchievementAdminListItem(
        **AchievementInfo.model_validate(achievement).model_dump(),
        details_summary={key: details[key] for key in summary_keys if key in details},
        proof_count=len(achievement.proofs),
        year=year,
    )


def _review_achievement(db: Session, achievement_id: int, target_status: str) -> Achievement:
    achievement = AchievementRepository.get_by_id(db, achievement_id)
    if not achievement:
        raise AppException("NOT_FOUND", "成果不存在", 404)
    if achievement.status != AchievementStatus.PENDING:
        raise AppException(
            "ACHIEVEMENT_REVIEW_CONFLICT",
            f"成果当前状态为 {achievement.status}，仅待审核成果可执行审核",
            409,
        )
    return AchievementRepository.update_status(db, achievement, target_status)


def _token_hash(token: str | None) -> str | None:
    return hashlib.sha256(token.encode("utf-8")).hexdigest() if token else None


def _audit_achievement_write(
    db: Session,
    *,
    user,
    action: str,
    target_id: int | None,
    result: str,
    token: str | None,
    error: str | None = None,
) -> None:
    AuditRepository.create(
        db,
        operator_id=user.id,
        operator_name=user.name,
        action=action,
        target_type="achievement",
        target_id=str(target_id) if target_id is not None else None,
        result=result,
        detail={"confirmation_token_hash": _token_hash(token), "error": error},
    )


def _verify_ai_confirmation(
    request: Request,
    *,
    operation: str,
    token: str | None,
    data: dict,
    user_id: int,
) -> None:
    is_ai_write = request.headers.get("X-AI-Skill", "").lower() == "achievement_manage"
    if is_ai_write or token:
        require_confirmation_token(operation, token, data, user_id)


@router.post("", response_model=AchievementInfo)
async def create_achievement(
    form: AchievementCreate,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    confirmation_data = form.model_dump(exclude_unset=True, exclude={"confirmation_token"})
    try:
        _verify_ai_confirmation(
            request,
            operation="achievement.create",
            token=form.confirmation_token,
            data=confirmation_data,
            user_id=current_user.id,
        )
        achievement = AchievementRepository.create(
            db,
            current_user.id,
            **_prepare_create_payload(form, current_user.id),
        )
        _audit_achievement_write(
            db,
            user=current_user,
            action="achievement.create",
            target_id=achievement.id,
            result="success",
            token=form.confirmation_token,
        )
        return achievement
    except Exception as exc:
        _audit_achievement_write(
            db,
            user=current_user,
            action="achievement.create",
            target_id=None,
            result="failed",
            token=form.confirmation_token,
            error=str(exc),
        )
        raise


@router.post("/files")
async def upload_achievement_file(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
):
    try:
        return AchievementFileService.upload(current_user.id, file)
    except ValueError as exc:
        raise AppException("ACHIEVEMENT_FILE_UPLOAD_FAILED", str(exc), 400) from exc


@router.get("/files/{file_id}")
async def get_achievement_file(
    file_id: str,
    download: bool = Query(False),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    safe_file_id = os.path.basename(file_id)
    if not safe_file_id or safe_file_id != file_id:
        raise AppException("ACHIEVEMENT_FILE_NOT_FOUND", "证明材料不存在", 404)

    reference = _find_proof_reference(db, safe_file_id, user_id=current_user.id)
    if not reference and current_user.is_admin:
        reference = _find_proof_reference(db, safe_file_id)
    if reference:
        owner_user_id, proof = reference
    else:
        owner_user_id, proof = current_user.id, {}

    try:
        path = AchievementFileService.get_path(owner_user_id, safe_file_id)
    except ValueError as exc:
        raise AppException("ACHIEVEMENT_FILE_NOT_FOUND", str(exc), 404) from exc

    original_name = os.path.basename(str(proof.get("name") or safe_file_id))
    media_type = mimetypes.guess_type(path)[0] or str(
        proof.get("mime") or "application/octet-stream"
    )
    return FileResponse(
        path=path,
        filename=original_name,
        media_type=media_type,
        content_disposition_type="attachment" if download else "inline",
    )


@router.get("/years", response_model=list[dict[str, int]])
async def list_achievement_years(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return AchievementRepository.list_years_by_user(db, current_user.id)


@router.get("", response_model=AchievementListResponse)
async def list_my_achievements(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    category: Optional[str] = None,
    status: Optional[str] = None,
    year: Optional[str] = Query(None, pattern=r"^\d{4}$"),
):
    items, total = AchievementRepository.list_by_user(
        db, current_user.id, page, page_size, category, status, year
    )
    return AchievementListResponse(total=total, items=[AchievementInfo.model_validate(a) for a in items])


@router.get("/public/list", response_model=AchievementListResponse)
async def list_public_achievements(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    category: Optional[str] = None,
    q: Optional[str] = None,
):
    items, total = AchievementRepository.list_public(db, page, page_size, category, q)
    return AchievementListResponse(total=total, items=[AchievementInfo.model_validate(a) for a in items])


@router.get("/admin/all", response_model=AchievementAdminListResponse)
async def admin_list_achievements(
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    status: Optional[str] = None,
    q: Optional[str] = None,
    category: Optional[str] = None,
    year: Optional[str] = Query(None, pattern=r"^\d{4}$"),
):
    items, total = AchievementRepository.list_all(
        db, page, page_size, status, q, category, year
    )
    return AchievementAdminListResponse(total=total, items=[_admin_list_item(a) for a in items])


@router.put("/admin/{achievement_id}/approve", response_model=AchievementInfo)
async def admin_approve_achievement(
    achievement_id: int,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return _review_achievement(db, achievement_id, AchievementStatus.APPROVED)


@router.put("/admin/{achievement_id}/reject", response_model=AchievementInfo)
async def admin_reject_achievement(
    achievement_id: int,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return _review_achievement(db, achievement_id, AchievementStatus.REJECTED)


# Static routes such as /years, /stats, and /files must stay above /{achievement_id}.
@router.get("/{achievement_id}", response_model=AchievementInfo)
async def get_achievement(
    achievement_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    achievement = AchievementRepository.get_by_id(db, achievement_id)
    if not achievement or (achievement.user_id != current_user.id and not current_user.is_admin):
        raise AppException("NOT_FOUND", "成果不存在", 404)
    return achievement


@router.put("/{achievement_id}", response_model=AchievementInfo)
async def update_achievement(
    achievement_id: int,
    form: AchievementUpdate,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    a = AchievementRepository.get_by_id_for_user(db, achievement_id, current_user.id)
    if not a:
        raise AppException("NOT_FOUND", "成果不存在", 404)
    confirmation_data = {
        "achievement_id": achievement_id,
        **form.model_dump(exclude_unset=True, exclude={"confirmation_token"}),
    }
    try:
        _verify_ai_confirmation(
            request,
            operation="achievement.update",
            token=form.confirmation_token,
            data=confirmation_data,
            user_id=current_user.id,
        )
        previous_proofs = list(a.proofs)
        payload = _prepare_update_payload(a, form, current_user.id)
        payload["status"] = AchievementStatus.PENDING
        achievement = AchievementRepository.update(db, a, **payload)
        if "proofs" in payload:
            AchievementFileService.delete_removed(
                current_user.id,
                previous_proofs,
                _remaining_user_proofs(db, current_user.id),
            )
        _audit_achievement_write(
            db,
            user=current_user,
            action="achievement.update",
            target_id=achievement.id,
            result="success",
            token=form.confirmation_token,
        )
        return achievement
    except Exception as exc:
        _audit_achievement_write(
            db,
            user=current_user,
            action="achievement.update",
            target_id=achievement_id,
            result="failed",
            token=form.confirmation_token,
            error=str(exc),
        )
        raise


@router.delete("/{achievement_id}", response_model=OperationResult)
async def delete_achievement(
    achievement_id: int,
    request: Request,
    confirmation_token: str | None = Query(None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    a = AchievementRepository.get_by_id_for_user(db, achievement_id, current_user.id)
    if not a:
        raise AppException("NOT_FOUND", "成果不存在", 404)
    confirmation_data = {"achievement_id": achievement_id}
    try:
        _verify_ai_confirmation(
            request,
            operation="achievement.delete",
            token=confirmation_token,
            data=confirmation_data,
            user_id=current_user.id,
        )
        previous_proofs = list(a.proofs)
        AchievementRepository.soft_delete(db, a)
        AchievementFileService.delete_removed(
            current_user.id,
            previous_proofs,
            _remaining_user_proofs(db, current_user.id),
        )
        _audit_achievement_write(
            db,
            user=current_user,
            action="achievement.delete",
            target_id=achievement_id,
            result="success",
            token=confirmation_token,
        )
        return OperationResult(success=True, message="成果已删除")
    except Exception as exc:
        _audit_achievement_write(
            db,
            user=current_user,
            action="achievement.delete",
            target_id=achievement_id,
            result="failed",
            token=confirmation_token,
            error=str(exc),
        )
        raise
