from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SessionInfo(BaseModel):
    id: int
    device_id: str
    device_name: Optional[str] = None
    ip: Optional[str] = None
    user_agent: Optional[str] = None
    issued_at: datetime
    last_active_at: datetime
    expires_at: datetime
    is_current: bool = False

    model_config = {"from_attributes": True}


class SessionListResponse(BaseModel):
    total: int
    items: list[SessionInfo]


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None  # 旋转时返回新 refresh
    token_type: str = "bearer"


class OperationResult(BaseModel):
    success: bool
    message: str
