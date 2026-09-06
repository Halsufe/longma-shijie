import json
import logging
import time

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.errors import AppException
from backend.app.repositories.skill_repo import SkillRepository, SkillCallRepository
from backend.app.schemas.skill import (
    SkillInfo,
    SkillUpdate,
    SkillListResponse,
    SkillCallInfo,
    SkillCallListResponse,
    SkillInvoke,
)
from backend.app.api.deps import require_admin

logger = logging.getLogger(__name__)
router = APIRouter()
_MODEL_CONFIG_KEYS = {"model", "temperature", "max_tokens", "top_p"}


def _validate_model_config(value: str | None) -> None:
    if value in (None, ""):
        return
    try:
        payload = json.loads(value or "")
    except (TypeError, json.JSONDecodeError) as exc:
        raise AppException("INVALID_MODEL_CONFIG", "模型配置必须是合法 JSON", 400) from exc
    if not isinstance(payload, dict) or set(payload) - _MODEL_CONFIG_KEYS:
        raise AppException("INVALID_MODEL_CONFIG", "模型配置包含不支持的字段", 400)
    if "temperature" in payload and not isinstance(payload["temperature"], (int, float)):
        raise AppException("INVALID_MODEL_CONFIG", "temperature 必须是数字", 400)
    if "max_tokens" in payload and (not isinstance(payload["max_tokens"], int) or payload["max_tokens"] < 1):
        raise AppException("INVALID_MODEL_CONFIG", "max_tokens 必须是正整数", 400)
    if "top_p" in payload and not isinstance(payload["top_p"], (int, float)):
        raise AppException("INVALID_MODEL_CONFIG", "top_p 必须是数字", 400)


def _skill_to_info(s) -> SkillInfo:
    try:
        triggers = json.loads(s.triggers) if s.triggers else []
    except (json.JSONDecodeError, TypeError):
        triggers = []
    return SkillInfo(
        id=s.id, name=s.name, display_name=s.display_name, triggers=triggers,
        description=s.description, category=s.category, is_enabled=s.is_enabled,
        is_system=s.is_system, model_config_json=s.model_config_json, created_at=s.created_at, updated_at=s.updated_at,
    )


@router.get("/skills", response_model=SkillListResponse)
async def list_skills(
    is_enabled: bool = Query(None),
    include_business: bool = Query(False),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    items = SkillRepository.list(db, is_enabled=is_enabled)
    if not include_business:
        items = [item for item in items if item.category != "business"]
    return SkillListResponse(total=len(items), items=[_skill_to_info(s) for s in items])


@router.put("/skills/{skill_id}", response_model=SkillInfo)
async def update_skill(
    skill_id: int,
    form: SkillUpdate,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    s = SkillRepository.get_by_id(db, skill_id)
    if not s:
        raise AppException("SKILL_NOT_FOUND", "Skill 不存在", 404)
    _validate_model_config(form.model_config_json)
    s = SkillRepository.update(
        db, s,
        display_name=form.display_name, triggers=form.triggers,
        description=form.description, is_enabled=form.is_enabled,
        model_config_json=form.model_config_json,
    )
    return _skill_to_info(s)


@router.post("/skills/{skill_id}/invoke")
async def invoke_skill(
    skill_id: int,
    form: SkillInvoke,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """直接调用指定 Skill（测试用，记录调用）"""
    from backend.app.ai.base import get_adapter
    from backend.app.ai.skill_dispatcher import skill_dispatcher

    s = SkillRepository.get_by_id(db, skill_id)
    if not s:
        raise AppException("SKILL_NOT_FOUND", "Skill 不存在", 404)
    if not s.is_enabled:
        raise AppException("SKILL_DISABLED", "Skill 已禁用", 400)

    start = time.time()
    system_prompt = skill_dispatcher.get_system_prompt(s.name, form.input)
    adapter = get_adapter()
    try:
        output = await adapter.chat(
            [{"role": "user", "content": form.input}], system_prompt=system_prompt
        )
        status = "success"
        error = None
    except Exception as e:
        output = None
        status = "failed"
        error = str(e)
        logger.exception("Skill invoke failed: %s", s.name)

    duration_ms = int((time.time() - start) * 1000)
    SkillCallRepository.create(
        db, skill_name=s.name, user_id=current_user.id,
        input=form.input, output=output, status=status,
        duration_ms=duration_ms, error=error,
    )
    return {
        "skill": s.name,
        "output": output,
        "status": status,
        "duration_ms": duration_ms,
        "model": adapter.name,
    }


@router.get("/skills/calls", response_model=SkillCallListResponse)
async def list_skill_calls(
    skill_name: str = Query(None),
    user_id: int = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),  # 上限由 normalize_page_size 静默截断到 100
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    items, total = SkillCallRepository.list(
        db, skill_name=skill_name, user_id=user_id, page=page, page_size=page_size
    )
    return SkillCallListResponse(total=total, items=[SkillCallInfo.model_validate(c) for c in items])
