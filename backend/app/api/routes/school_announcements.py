from __future__ import annotations

from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.database import get_db
from backend.app.repositories.announcement_repo import AnnouncementRepository
from backend.app.schemas.announcement import AnnouncementInfo, AnnouncementListResponse, AnnouncementSourceInfo, DigestInfo
from backend.app.models.announcement import AnnouncementDigest, AnnouncementOrigin

router = APIRouter()


@router.get("/school-announcements", response_model=AnnouncementListResponse)
async def list_school_announcements(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), keyword: str | None = Query(None, max_length=100),
    source_id: int | None = Query(None, ge=1), published_from: date | None = None, published_to: date | None = None,
    current_user=Depends(get_current_user), db: Session = Depends(get_db),
):
    items, total = AnnouncementRepository.list_visible(db, page=page, page_size=page_size, keyword=keyword, source_id=source_id, published_from=published_from, published_to=published_to)
    response_items = []
    for item in items:
        payload = AnnouncementInfo.model_validate(item).model_dump()
        origin = db.query(AnnouncementOrigin).filter(AnnouncementOrigin.announcement_id == item.id).order_by(AnnouncementOrigin.id).first()
        payload["original_url"] = origin.canonical_url if origin else None
        response_items.append(AnnouncementInfo(**payload))
    return AnnouncementListResponse(total=total, page=page, page_size=page_size, items=response_items)


@router.get("/school-announcements/sources", response_model=list[AnnouncementSourceInfo])
async def list_school_announcement_sources(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return [AnnouncementSourceInfo.model_validate(item) for item in AnnouncementRepository.list_sources(db, enabled_only=True)]


@router.get("/school-announcement-digests/{digest_id}", response_model=DigestInfo)
async def get_school_announcement_digest(digest_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    digest = db.query(AnnouncementDigest).filter(AnnouncementDigest.id == digest_id).first()
    if not digest:
        from backend.app.core.errors import AppException
        raise AppException("DIGEST_NOT_FOUND", "公告汇总不存在", 404)
    allowed = db.query(AnnouncementDigest).filter(AnnouncementDigest.id == digest_id).first()
    return DigestInfo.model_validate(allowed)
