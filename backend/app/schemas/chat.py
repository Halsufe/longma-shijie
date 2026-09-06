from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


class SessionCreate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    knowledge_scope: str = Field("personal")
    web_search_enabled: bool = True

    @field_validator("knowledge_scope")
    @classmethod
    def validate_scope(cls, value: str) -> str:
        from backend.app.services.knowledge_scope import KnowledgeScopeGuard
        return KnowledgeScopeGuard.parse(value).value


class SessionUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    knowledge_scope: Optional[str] = None
    web_search_enabled: Optional[bool] = None

    @field_validator("knowledge_scope")
    @classmethod
    def validate_update_scope(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        from backend.app.services.knowledge_scope import KnowledgeScopeGuard
        return KnowledgeScopeGuard.parse(value).value


class SessionInfo(BaseModel):
    id: int
    user_id: int
    title: str
    created_at: datetime
    updated_at: datetime
    last_message_preview: Optional[str] = None
    knowledge_scope: str = "personal"
    web_search_enabled: bool = True
    last_message_status: Optional[str] = None

    model_config = {"from_attributes": True}


class SessionListResponse(BaseModel):
    total: int
    items: list[SessionInfo]


class MessageInfo(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    skill_name: Optional[str] = None
    token_usage: Optional[int] = None
    duration_ms: Optional[int] = None
    citations: Optional[str] = None
    regenerated_at: Optional[datetime] = None
    created_at: datetime
    knowledge_scope: Optional[str] = None
    request_id: Optional[str] = None
    status: str = "completed"
    partial_content: Optional[str] = None
    last_event_id: int = 0
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    completed_at: Optional[datetime] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None

    model_config = {"from_attributes": True}


class MessageListResponse(BaseModel):
    total: int
    items: list[MessageInfo]


class MessageSend(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)
    skill: Optional[str] = Field(None, description="指定 Skill 名称，如 @总结")
    rag_scope: str = Field("personal", description="兼容字段；取值为 none/personal/class")
    knowledge_scope: Optional[str] = None
    web_search_enabled: bool = True
    idempotency_key: Optional[str] = Field(None, max_length=200)

    @field_validator("knowledge_scope")
    @classmethod
    def validate_knowledge_scope(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        from backend.app.services.knowledge_scope import KnowledgeScopeGuard
        return KnowledgeScopeGuard.parse(value).value
