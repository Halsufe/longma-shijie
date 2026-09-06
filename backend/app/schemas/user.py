from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, Any
from datetime import datetime


ROLE_PATTERN = r"^(student|alumni|teacher|admin)$"


class UserLogin(BaseModel):
    student_no: str = Field(..., min_length=1, max_length=50, description="学号")
    password: str = Field(..., min_length=1, max_length=128, description="密码")


class UserLoginResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    user: dict


class ChangePassword(BaseModel):
    old_password: str = Field(..., min_length=1, description="旧密码")
    new_password: str = Field(..., min_length=8, max_length=128, description="新密码")


class UserInfo(BaseModel):
    id: int
    student_no: str
    name: str
    role: str
    status: str
    graduation_year: Optional[int] = None
    profile: Optional[dict] = None
    party: Optional[dict] = None
    political_status: str = "群众"
    political_status_updated_at: Optional[datetime] = None
    last_active_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

    @field_validator("political_status", mode="before")
    @classmethod
    def default_political_status(cls, value):
        return value or "群众"


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    graduation_year: Optional[int] = None
    profile: Optional[dict[str, Any]] = None


class CourseGrade(BaseModel):
    course_name: str = Field(..., min_length=1)
    score: str = Field(..., min_length=1)
    remark: Optional[str] = None


class AlumniConversionRequestCreate(BaseModel):
    graduation_year: int = Field(..., ge=1950, le=2100)


class AlumniConversionRequestInfo(BaseModel):
    id: int
    user_id: int
    graduation_year: int
    status: str
    review_comment: Optional[str] = None
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class AlumniReview(BaseModel):
    comment: Optional[str] = Field(None, max_length=1000)


class UserCreate(BaseModel):
    student_no: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(default="student", pattern=ROLE_PATTERN)


class UserResetPassword(BaseModel):
    new_password: Optional[str] = Field(None, max_length=128)


class AdminUserCreate(BaseModel):
    student_no: str
    name: str
    role: str = "student"


class UserListResponse(BaseModel):
    total: int
    items: list[UserInfo]


class OperationResult(BaseModel):
    success: bool
    message: str
