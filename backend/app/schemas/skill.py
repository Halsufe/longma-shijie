from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class SkillInfo(BaseModel):
    id: int
    name: str
    display_name: str
    triggers: list[str]
    description: Optional[str] = None
    category: str
    is_enabled: bool
    is_system: bool
    model_config_json: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SkillUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=100)
    triggers: Optional[list[str]] = None
    description: Optional[str] = None
    is_enabled: Optional[bool] = None
    model_config_json: Optional[str] = Field(None, max_length=2000)


class SkillListResponse(BaseModel):
    total: int
    items: list[SkillInfo]


class SkillCallInfo(BaseModel):
    id: int
    skill_name: str
    user_id: Optional[int] = None
    input: str
    output: Optional[str] = None
    status: str
    duration_ms: Optional[int] = None
    token_usage: Optional[int] = None
    error: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SkillCallListResponse(BaseModel):
    total: int
    items: list[SkillCallInfo]


class SkillInvoke(BaseModel):
    """直接调用 Skill（测试用）"""
    skill_name: str
    input: str = Field(..., max_length=10000)
