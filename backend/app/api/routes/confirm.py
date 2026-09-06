"""
任务确认 API 路由

提供通用的"预览→确认→执行"两阶段提交接口。

使用方式：
1. POST /api/v1/confirm/preview — 提交操作和数据，获取确认令牌和预览
2. 用户查看预览内容
3. POST /api/v1/confirm/verify — 验证确认令牌（可选，用于前端校验）
4. 前端携带确认令牌调用实际业务接口

也支持直接在业务接口中使用 ConfirmationManager：
    confirmation = ConfirmationManager.create_confirmation(user.id, "resource.create", data)
    return {"preview": ..., **confirmation}
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.api.deps import get_current_user
from backend.app.core.confirmation import (
    ConfirmationManager,
    is_confirmable,
    get_operation_description,
)

router = APIRouter()


class PreviewRequest(BaseModel):
    """预览请求"""
    operation: str = Field(..., description="操作类型（如 resource.create）")
    data: Dict[str, Any] = Field(default_factory=dict, description="操作数据")


class VerifyRequest(BaseModel):
    """验证请求"""
    confirmation_token: str
    operation: str
    data: Dict[str, Any] = Field(default_factory=dict)


@router.post("/preview")
async def preview_operation(
    form: PreviewRequest,
    current_user=Depends(get_current_user),
):
    """
    预览操作（生成确认令牌）

    返回确认令牌和数据预览，用户确认后携带令牌调用业务接口。
    """
    from backend.app.core.errors import AppException

    if not is_confirmable(form.operation):
        raise AppException(
            "CONFIRMATION_INVALID",
            f"操作 '{form.operation}' 不需要确认或未注册",
            400,
        )

    description = get_operation_description(form.operation)
    confirmation = ConfirmationManager.create_confirmation(
        current_user.id, form.operation, form.data
    )
    preview = ConfirmationManager.build_preview(form.operation, form.data, description)

    return {
        "preview": preview,
        **confirmation,
    }


@router.post("/verify")
async def verify_confirmation(
    form: VerifyRequest,
    current_user=Depends(get_current_user),
):
    """
    验证确认令牌

    前端在执行操作前可调用此接口验证令牌有效性。
    """
    result = ConfirmationManager.verify_confirmation(
        form.confirmation_token, current_user.id, form.operation, form.data
    )
    return {
        "valid": True,
        "operation": form.operation,
        "description": get_operation_description(form.operation),
    }


@router.get("/operations")
async def list_confirmable_operations(
    current_user=Depends(get_current_user),
):
    """列出所有需要确认的操作类型"""
    from backend.app.core.confirmation import _CONFIRMABLE_OPERATIONS
    return {
        "total": len(_CONFIRMABLE_OPERATIONS),
        "operations": [
            {"operation": op, "description": desc}
            for op, desc in _CONFIRMABLE_OPERATIONS.items()
        ],
    }
