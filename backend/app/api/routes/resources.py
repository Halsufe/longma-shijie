from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from typing import Optional, List

from backend.app.core.database import get_db
from backend.app.repositories.resource_repo import ResourceRepository
from backend.app.api.deps import get_current_user, require_admin
from backend.app.schemas.resource import (
    ResourceCreate, ResourceUpdate, ResourceInfo, ResourceListResponse
)
from backend.app.schemas.user import OperationResult
from backend.app.services.confirmation_adapter import verify_optional_confirmation

router = APIRouter()


@router.post("", response_model=ResourceInfo)
async def create_resource(
    form: ResourceCreate,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payload = form.model_dump(exclude_unset=True, exclude={"confirmation_token"})
    verify_optional_confirmation(db, request, "resource.create", payload, form.confirmation_token, current_user)
    return ResourceRepository.create(db, current_user.id, **payload)


@router.get("", response_model=ResourceListResponse)
async def list_resources(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    type: Optional[str] = None,
    q: Optional[str] = None,
    tag: Optional[str] = None,
):
    items, total = ResourceRepository.list_approved(db, page, page_size, type, q, tag)
    return ResourceListResponse(total=total, items=[ResourceInfo.model_validate(r) for r in items])


@router.get("/mine", response_model=ResourceListResponse)
async def list_my_resources(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
):
    items, total = ResourceRepository.list_by_author(db, current_user.id, page, page_size)
    return ResourceListResponse(total=total, items=[ResourceInfo.model_validate(r) for r in items])


@router.get("/favorites", response_model=ResourceListResponse)
async def list_favorites(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
):
    items, total = ResourceRepository.list_favorites(db, current_user.id, page, page_size)
    return ResourceListResponse(total=total, items=[ResourceInfo.model_validate(r) for r in items])


@router.get("/{resource_id}", response_model=ResourceInfo)
async def get_resource(
    resource_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from backend.app.core.errors import AppException
    r = ResourceRepository.get_by_id(db, resource_id)
    if not r:
        raise AppException("NOT_FOUND", "资源不存在", 404)
    ResourceRepository.increment_view(db, r)
    return r


@router.put("/{resource_id}", response_model=ResourceInfo)
async def update_resource(
    resource_id: int,
    form: ResourceUpdate,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from backend.app.core.errors import AppException
    r = ResourceRepository.get_by_id(db, resource_id)
    if not r or r.author_id != current_user.id:
        raise AppException("NOT_FOUND", "资源不存在", 404)
    payload = {"resource_id": resource_id, **form.model_dump(exclude_unset=True, exclude={"confirmation_token"})}
    verify_optional_confirmation(db, request, "resource.update", payload, form.confirmation_token, current_user)
    payload.pop("resource_id")
    return ResourceRepository.update(db, r, **payload)


@router.delete("/{resource_id}", response_model=OperationResult)
async def delete_resource(
    resource_id: int,
    request: Request,
    confirmation_token: str | None = Query(None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from backend.app.core.errors import AppException
    r = ResourceRepository.get_by_id(db, resource_id)
    if not r or r.author_id != current_user.id:
        raise AppException("NOT_FOUND", "资源不存在", 404)
    verify_optional_confirmation(db, request, "resource.delete", {"resource_id": resource_id}, confirmation_token, current_user)
    ResourceRepository.soft_delete(db, r)
    return OperationResult(success=True, message="资源已删除")


@router.post("/{resource_id}/favorite", response_model=OperationResult)
async def favorite_resource(
    resource_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ResourceRepository.favorite(db, current_user.id, resource_id)
    return OperationResult(success=True, message="已收藏")


@router.delete("/{resource_id}/favorite", response_model=OperationResult)
async def unfavorite_resource(
    resource_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ResourceRepository.unfavorite(db, current_user.id, resource_id)
    return OperationResult(success=True, message="已取消收藏")


@router.post("/{resource_id}/like", response_model=OperationResult)
async def like_resource(
    resource_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ResourceRepository.like(db, current_user.id, resource_id)
    return OperationResult(success=True, message="已点赞")


@router.delete("/{resource_id}/like", response_model=OperationResult)
async def unlike_resource(
    resource_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ResourceRepository.unlike(db, current_user.id, resource_id)
    return OperationResult(success=True, message="已取消点赞")


@router.get("/admin/pending", response_model=ResourceListResponse)
async def admin_list_pending(
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
):
    items, total = ResourceRepository.list_by_status(db, "pending", page, page_size)
    return ResourceListResponse(total=total, items=[ResourceInfo.model_validate(r) for r in items])


@router.put("/admin/{resource_id}/approve", response_model=ResourceInfo)
async def admin_approve_resource(
    resource_id: int,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return ResourceRepository.update_status(db, resource_id, "approved")


@router.put("/admin/{resource_id}/reject", response_model=ResourceInfo)
async def admin_reject_resource(
    resource_id: int,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return ResourceRepository.update_status(db, resource_id, "rejected")
