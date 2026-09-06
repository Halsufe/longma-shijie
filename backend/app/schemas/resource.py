from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ResourceCreate(BaseModel):
    type: str = Field(..., min_length=1, max_length=30)
    title: str = Field(..., min_length=1, max_length=200)
    content: Optional[str] = None
    tags: Optional[List[str]] = None
    attachments: Optional[List[dict]] = None
    deadline: Optional[datetime] = None
    source: Optional[str] = None
    confirmation_token: Optional[str] = None


class ResourceUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = None
    tags: Optional[List[str]] = None
    attachments: Optional[List[dict]] = None
    deadline: Optional[datetime] = None
    source: Optional[str] = None
    confirmation_token: Optional[str] = None


class ResourceInfo(BaseModel):
    id: int
    author_id: int
    type: str
    title: str
    content: Optional[str] = None
    tags: List[str] = []
    attachments: List[dict] = []
    status: str
    view_count: int
    like_count: int
    deadline: Optional[datetime] = None
    source: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ResourceListResponse(BaseModel):
    total: int
    items: list[ResourceInfo]
