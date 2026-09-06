from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, require_admin
from backend.app.core.database import get_db
from backend.app.core.errors import AppException
from backend.app.models.token_quota import (
    ChatTokenUsageEvent,
    TokenQuotaAuditLog,
    TokenQuotaPolicy,
    UserDailyTokenUsage,
)
from backend.app.models.user import User
from backend.app.services.chat_quota_service import ChatQuotaService, VALID_QUOTA_ROLES
from backend.app.services.token_quota_service import usage_date
from backend.app.services.admin_scope_service import can_manage_user, managed_class_ids, user_class_id

router = APIRouter()


class PolicyUpdate(BaseModel):
    daily_limit: int = Field(ge=0)
    reason: str = Field(min_length=1, max_length=500)


class OverrideUpdate(PolicyUpdate):
    valid_until: datetime | None = None


class UsageReconcile(BaseModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


@router.get("/chat/usage/me")
def my_chat_usage(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return ChatQuotaService.usage_summary(db, current_user)


@router.get("/admin/chat/quota-policies")
def list_quota_policies(current_user=Depends(require_admin), db: Session = Depends(get_db)):
    rows = {row.role: row for row in db.query(TokenQuotaPolicy).all()}
    return [
        {
            "role": role,
            "daily_limit": rows[role].daily_limit if role in rows else 0,
            "model": rows[role].model if role in rows else "deepseek-v4-flash",
            "enabled": rows[role].enabled if role in rows else False,
            "configured": role in rows,
            "version": rows[role].version if role in rows else 0,
            "updated_at": rows[role].updated_at if role in rows else None,
        }
        for role in sorted(VALID_QUOTA_ROLES)
    ]


@router.put("/admin/chat/quota-policies/{role}")
def update_quota_policy(role: str, form: PolicyUpdate, current_user=Depends(require_admin), db: Session = Depends(get_db)):
    try:
        row = ChatQuotaService.update_policy(db, role=role, daily_limit=form.daily_limit, changed_by=current_user.id, reason=form.reason)
    except ValueError as exc:
        raise AppException(str(exc), "额度策略参数无效", 400) from exc
    return {"role": row.role, "daily_limit": row.daily_limit, "model": row.model, "version": row.version, "updated_at": row.updated_at}


@router.put("/admin/users/{user_id}/chat-quota")
def update_user_quota(user_id: int, form: OverrideUpdate, current_user=Depends(require_admin), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
    if not target:
        raise AppException("USER_NOT_FOUND", "用户不存在", 404)
    if not can_manage_user(current_user, target):
        raise AppException("FORBIDDEN", "目标用户不在管理员管理范围内", 403)
    try:
        row = ChatQuotaService.set_override(
            db, user_id=user_id, daily_limit=form.daily_limit, changed_by=current_user.id,
            reason=form.reason, valid_until=form.valid_until,
        )
    except ValueError as exc:
        raise AppException(str(exc), "用户额度参数无效", 400) from exc
    return {"user_id": row.user_id, "daily_limit": row.daily_limit, "valid_from": row.valid_from, "valid_until": row.valid_until}


@router.get("/admin/users/{user_id}/chat-quota/audit")
def user_quota_audit(user_id: int, current_user=Depends(require_admin), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
    if not target:
        raise AppException("USER_NOT_FOUND", "用户不存在", 404)
    if not can_manage_user(current_user, target):
        raise AppException("FORBIDDEN", "目标用户不在管理员管理范围内", 403)
    rows = db.query(TokenQuotaAuditLog).filter(TokenQuotaAuditLog.target_user_id == user_id).order_by(TokenQuotaAuditLog.id.desc()).all()
    return [{"id": row.id, "old_limit": row.old_limit, "new_limit": row.new_limit, "changed_by": row.changed_by, "reason": row.reason, "created_at": row.created_at} for row in rows]


@router.get("/admin/chat/usage")
def admin_chat_usage(
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100),
    current_user=Depends(require_admin), db: Session = Depends(get_db),
):
    query = db.query(UserDailyTokenUsage, User).join(User, User.id == UserDailyTokenUsage.user_id)
    allowed = managed_class_ids(current_user)
    rows_all: list[tuple[UserDailyTokenUsage, User]] = [
        (usage, user)
        for usage, user in query.order_by(
            UserDailyTokenUsage.usage_date.desc(), UserDailyTokenUsage.id.desc()
        ).all()
    ]
    if allowed is not None:
        rows_all = [(usage, user) for usage, user in rows_all if user_class_id(user) in allowed]
    total = len(rows_all)
    rows = rows_all[(page - 1) * page_size : page * page_size]
    settled_total = sum(int(usage.total_tokens or 0) for usage, _ in rows_all)
    pending_total = sum(int(usage.pending_reconciliation or 0) for usage, _ in rows_all)
    return {
        "total": total,
        "settled_tokens": settled_total,
        "pending_reconciliation": pending_total,
        "items": [{
            "user_id": usage.user_id, "user_name": user.name, "usage_date": usage.usage_date,
            "quota": usage.quota_snapshot, "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens, "total_tokens": usage.total_tokens,
            "pending_reconciliation": usage.pending_reconciliation,
        } for usage, user in rows],
    }


@router.get("/admin/chat/user-quotas")
def admin_user_quotas(current_user=Depends(require_admin), db: Session = Depends(get_db)):
    """Return today's quota state for every manageable active user.

    Unlike the usage ledger endpoint this also includes users who have not
    started a chat today, so an administrator can configure a first override
    without needing a prior conversation.
    """
    allowed = managed_class_ids(current_user)
    users = db.query(User).filter(User.deleted_at.is_(None), User.status == "active").order_by(User.name.asc()).all()
    if allowed is not None:
        users = [user for user in users if user_class_id(user) in allowed]
    day = usage_date()
    usage_rows = {
        row.user_id: row
        for row in db.query(UserDailyTokenUsage).filter(UserDailyTokenUsage.usage_date == day).all()
    }
    items = []
    for user in users:
        usage = usage_rows.get(user.id)
        quota = ChatQuotaService.effective_quota(db, user)
        items.append({
            "user_id": user.id,
            "user_name": user.name,
            "student_no": user.student_no,
            "role": user.role,
            "quota": quota,
            "used_tokens": usage.total_tokens if usage else 0,
            "pending_reconciliation": usage.pending_reconciliation if usage else 0,
            "remaining_tokens": max(0, quota - (usage.total_tokens if usage else 0) - (usage.pending_reconciliation if usage else 0)),
        })
    return {"total": len(items), "items": items}


@router.get("/admin/chat/reconciliation")
def pending_reconciliation(
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100),
    current_user=Depends(require_admin), db: Session = Depends(get_db),
):
    rows, total = ChatQuotaService.pending_events(db, page=page, page_size=page_size)
    return {"total": total, "items": [{
        "id": row.id, "request_id": row.request_id, "user_id": row.user_id,
        "attempt_no": row.attempt_no, "status": row.status, "error_code": row.error_code,
        "created_at": row.created_at,
    } for row in rows]}


@router.post("/admin/chat/reconciliation/{event_id}")
def reconcile_usage(event_id: int, form: UsageReconcile, current_user=Depends(require_admin), db: Session = Depends(get_db)):
    try:
        row = ChatQuotaService.reconcile_event(
            db, event_id, input_tokens=form.input_tokens, output_tokens=form.output_tokens,
        )
    except ValueError as exc:
        raise AppException(str(exc), "usage 对账失败", 400) from exc
    return {"id": row.id, "request_id": row.request_id, "status": row.status, "total_tokens": row.total_tokens}
