import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.repositories.audit_repo import AuditRepository
from backend.app.schemas.audit import AuditLogInfo, AuditLogListResponse
from backend.app.api.deps import require_admin

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/audit", response_model=AuditLogListResponse)
async def list_audit_logs(
    operator_id: int = Query(None),
    action: str = Query(None),
    target_type: str = Query(None),
    start: datetime = Query(None),
    end: datetime = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    items, total = AuditRepository.list(
        db, operator_id=operator_id, action=action, target_type=target_type,
        start=start, end=end, page=page, page_size=page_size,
    )
    return AuditLogListResponse(total=total, items=[AuditLogInfo.model_validate(i) for i in items])
