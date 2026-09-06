from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class DirectionCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    tags: Optional[List[str]] = None


class DirectionUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None


class DirectionInfo(BaseModel):
    id: int
    teacher_id: int
    title: str
    description: Optional[str] = None
    tags: List[str] = []
    is_active: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DirectionListResponse(BaseModel):
    total: int
    items: list[DirectionInfo]


class TeacherInfo(BaseModel):
    id: int
    student_no: str
    name: str
    role: str
    graduation_year: Optional[int] = None
    profile: Optional[dict] = None
    direction_count: int = 0

    model_config = {"from_attributes": True}


class TeacherListResponse(BaseModel):
    total: int
    items: list[TeacherInfo]


class ApplicationCreate(BaseModel):
    teacher_id: int
    title: str = Field(..., min_length=1, max_length=200)
    message: Optional[str] = None
    direction_id: Optional[int] = None
    related_achievement_id: Optional[int] = None
    related_resource_id: Optional[int] = None


class ApplicationInfo(BaseModel):
    id: int
    student_id: int
    teacher_id: int
    direction_id: Optional[int] = None
    title: str
    message: Optional[str] = None
    status: str
    related_achievement_id: Optional[int] = None
    related_resource_id: Optional[int] = None
    decided_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ApplicationListResponse(BaseModel):
    total: int
    items: list[ApplicationInfo]


class PlanCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    items: Optional[List[dict]] = None
    reminder_at: Optional[datetime] = None


class PlanUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    items: Optional[List[dict]] = None
    reminder_at: Optional[datetime] = None
    is_completed: Optional[bool] = None


class PlanInfo(BaseModel):
    id: int
    user_id: int
    title: str
    description: Optional[str] = None
    items: List[dict] = []
    reminder_at: Optional[datetime] = None
    is_completed: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PlanListResponse(BaseModel):
    total: int
    items: list[PlanInfo]
