from typing import Any, Optional
from datetime import datetime

from pydantic import BaseModel, Field


class AchievementCreate(BaseModel):
    confirmation_token: Optional[str] = Field(None, exclude=True)
    title: str = Field(..., min_length=1, max_length=200)
    category: str = Field(..., min_length=1, max_length=30)
    description: Optional[str] = None
    achievement_date: Optional[str] = None
    level: Optional[str] = None
    is_public: bool = False
    member_ids: Optional[list[int]] = None
    proofs: Optional[list[dict[str, Any]]] = None
    details: Optional[dict[str, Any]] = None


class AchievementUpdate(BaseModel):
    confirmation_token: Optional[str] = Field(None, exclude=True)
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    category: Optional[str] = Field(None, min_length=1, max_length=30)
    description: Optional[str] = None
    achievement_date: Optional[str] = None
    level: Optional[str] = None
    is_public: Optional[bool] = None
    member_ids: Optional[list[int]] = None
    proofs: Optional[list[dict[str, Any]]] = None
    details: Optional[dict[str, Any]] = None


class AchievementInfo(BaseModel):
    id: int
    user_id: int
    category: str
    title: str
    description: Optional[str] = None
    achievement_date: Optional[str] = None
    level: Optional[str] = None
    status: str
    is_public: bool
    member_ids: list[int] = Field(default_factory=list)
    proofs: list[dict[str, Any]] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AchievementListResponse(BaseModel):
    total: int
    items: list[AchievementInfo]


class AchievementAdminListItem(AchievementInfo):
    details_summary: dict[str, Any] = Field(default_factory=dict)
    proof_count: int = 0
    year: Optional[int] = None


class AchievementAdminListResponse(BaseModel):
    total: int
    items: list[AchievementAdminListItem]
