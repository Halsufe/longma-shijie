from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class FileInfo(BaseModel):
    id: int
    owner_user_id: int
    folder_id: Optional[int] = None
    scope: str
    class_id: Optional[int] = None
    original_name: str
    stored_name: str
    mime_type: str
    size: int
    parse_status: str
    parse_error: Optional[str] = None
    version: int
    download_count: int
    tag: Optional[str] = None
    is_pinned: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FileListResponse(BaseModel):
    total: int
    items: list[FileInfo]


class FileUpdate(BaseModel):
    original_name: Optional[str] = None
    tag: Optional[str] = None
    is_pinned: Optional[bool] = None
    folder_id: Optional[int] = None


class FolderCreate(BaseModel):
    name: str


class FolderInfo(BaseModel):
    id: int
    scope: str
    owner_user_id: int
    name: str
    created_by: int
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class FolderListResponse(BaseModel):
    items: list[FolderInfo]


class FileVersionInfo(BaseModel):
    id: int
    file_id: int
    version: int
    stored_name: str
    original_name: str
    mime_type: str
    size: int
    uploaded_by: int
    uploaded_at: datetime
    model_config = {"from_attributes": True}


class ChunkInfo(BaseModel):
    id: int
    file_id: int
    chunk_index: int
    page_no: Optional[int] = None
    content: str
    token_count: Optional[int] = None

    model_config = {"from_attributes": True}


class QuotaInfo(BaseModel):
    used_bytes: int
    quota_bytes: int
    used_mb: float
    quota_mb: float
    percentage: float


class SearchResult(BaseModel):
    file_id: int
    file_name: str
    chunk_content: str
    page_no: Optional[int] = None
    score: float
