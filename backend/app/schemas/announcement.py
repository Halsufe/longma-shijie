from datetime import date, datetime
from pydantic import BaseModel, Field


class AnnouncementSourceInfo(BaseModel):
    id: int
    code: str
    name: str
    list_url: str
    display_order: int
    enabled: bool
    model_config = {"from_attributes": True}


class AnnouncementInfo(BaseModel):
    id: int
    title: str
    published_at: date
    summary_text: str | None = None
    relevance_status: str
    status: str
    retention_until: date | None = None
    original_url: str | None = None
    model_config = {"from_attributes": True}


class AnnouncementListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[AnnouncementInfo]


class DigestInfo(BaseModel):
    id: int
    window_start: datetime
    window_end: datetime
    notification_text: str
    snapshot_json: str
    status: str
    is_recovery: bool
    model_config = {"from_attributes": True}
