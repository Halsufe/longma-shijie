import logging

from fastapi import APIRouter, Depends

from backend.app.schemas.audit import SystemConfigInfo, SystemConfigUpdate
from backend.app.api.deps import require_admin
from backend.app.core.database import get_db
from backend.app.core.errors import AppException
from backend.app.services.runtime_config_service import RuntimeConfigService
from backend.app.repositories.audit_repo import AuditRepository
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/config", response_model=SystemConfigInfo)
async def get_config(current_user=Depends(require_admin), db: Session = Depends(get_db)):
    """获取系统配置"""
    values = RuntimeConfigService.load(db)
    from backend.app.core.config import settings
    return SystemConfigInfo(**values, ai_api_key_configured=bool(settings.AI_API_KEY))


@router.put("/config", response_model=SystemConfigInfo)
async def update_config(
    form: SystemConfigUpdate,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        values = RuntimeConfigService.update(db, form.model_dump(exclude_none=True), current_user.id)
    except ValueError as exc:
        raise AppException("CONFIG_INVALID", str(exc), 400)
    AuditRepository.create(db, operator_id=current_user.id, operator_name=current_user.name,
                           action="admin.config.update", target_type="runtime_config",
                           detail={"keys": sorted(form.model_dump(exclude_none=True))})
    from backend.app.core.config import settings
    logger.info("System config persisted by admin user_id=%s", current_user.id)
    return SystemConfigInfo(**values, ai_api_key_configured=bool(settings.AI_API_KEY))
