from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from backend.app.core.confirmation import ConfirmationManager
from backend.app.core.errors import AppException
from backend.app.repositories.audit_repo import AuditRepository


def verify_optional_confirmation(
    db: Session, request: Request, operation: str, target_payload: Any, token: str | None, user
) -> None:
    if not token:
        return
    try:
        ConfirmationManager.verify_confirmation(token, user.id, operation, target_payload)
        result, error = "success", None
    except Exception as exc:
        result, error = "failed", str(exc)
        AuditRepository.create(db, operator_id=user.id, operator_name=user.name, action="confirmation.verify", target_type=operation, result=result, detail={"error": error})
        raise AppException("CONFIRMATION_INVALID", "确认令牌无效或数据已变更", 400) from exc
    AuditRepository.create(db, operator_id=user.id, operator_name=user.name, action="confirmation.verify", target_type=operation, result=result)
