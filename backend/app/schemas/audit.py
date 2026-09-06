from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class AuditLogInfo(BaseModel):
    id: int
    operator_id: Optional[int] = None
    operator_name: Optional[str] = None
    action: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    result: str
    ip: Optional[str] = None
    user_agent: Optional[str] = None
    detail: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    total: int
    items: list[AuditLogInfo]


class SystemStats(BaseModel):
    """系统统计"""
    users: dict
    chat: dict
    knowledge: dict
    skills: dict
    assignments: dict


class SystemConfigInfo(BaseModel):
    """系统配置"""
    class_name: str
    default_quota_mb: int
    ai_model: str
    ai_base_url: str = ""
    ai_api_key_configured: bool = False
    login_max_attempts: int
    login_window_minutes: int
    assignment_reminder_hours: list[int] = [24, 2]


class SystemConfigUpdate(BaseModel):
    class_name: Optional[str] = None
    default_quota_mb: Optional[int] = None
    login_max_attempts: Optional[int] = None
    login_window_minutes: Optional[int] = None
    ai_model: Optional[str] = None
    ai_base_url: Optional[str] = None
    assignment_reminder_hours: Optional[list[int]] = None


class StorageUsageInfo(BaseModel):
    """存储用量"""
    personal_total_bytes: int
    class_total_bytes: int
    by_user: list[dict]  # [{user_id, name, bytes, count}]
