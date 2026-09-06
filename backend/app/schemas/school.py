from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ========== 课程 ==========
class CourseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    teacher: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    color: Optional[str] = Field(None, max_length=20)
    semester: Optional[str] = Field(None, max_length=50)


class CourseUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    teacher: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    semester: Optional[str] = None


class CourseInfo(BaseModel):
    id: int
    name: str
    teacher: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    semester: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CourseListResponse(BaseModel):
    total: int
    items: list[CourseInfo]


# ========== 课程安排 ==========
class ScheduleCreate(BaseModel):
    weekday: int = Field(..., ge=1, le=7)
    start_period: int = Field(..., ge=1, le=12)
    end_period: int = Field(..., ge=1, le=12)
    start_time: Optional[str] = Field(None, max_length=10)
    end_time: Optional[str] = Field(None, max_length=10)
    location: Optional[str] = Field(None, max_length=100)
    weeks_pattern: Optional[str] = Field(None, max_length=100)


class ScheduleInfo(BaseModel):
    id: int
    course_id: int
    weekday: int
    start_period: int
    end_period: int
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    location: Optional[str] = None
    weeks_pattern: Optional[str] = None

    model_config = {"from_attributes": True}


class CourseWithSchedules(BaseModel):
    """课程 + 时间安排（课表展示）"""
    course: CourseInfo
    schedules: list[ScheduleInfo]


# ========== 作业 ==========
class AssignmentCreate(BaseModel):
    course_id: int
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    due_at: Optional[datetime] = None
    total_score: int = Field(100, ge=1, le=1000)
    attachment_url: Optional[str] = Field(None, max_length=500)


class AssignmentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    due_at: Optional[datetime] = None
    total_score: Optional[int] = Field(None, ge=1, le=1000)
    attachment_url: Optional[str] = None


class AssignmentInfo(BaseModel):
    id: int
    course_id: int
    title: str
    description: Optional[str] = None
    due_at: Optional[datetime] = None
    total_score: int
    status: str
    attachment_url: Optional[str] = None
    created_by: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AssignmentListResponse(BaseModel):
    total: int
    items: list[AssignmentInfo]


# ========== 提交 ==========
class SubmissionCreate(BaseModel):
    content: str = Field("", max_length=20000)
    attachment_name: Optional[str] = Field(None, max_length=255)


class SubmissionGrade(BaseModel):
    score: int = Field(..., ge=0, le=1000)
    feedback: Optional[str] = None


class SubmissionInfo(BaseModel):
    id: int
    assignment_id: int
    user_id: int
    content: str
    attachment_name: Optional[str] = None
    score: Optional[int] = None
    feedback: Optional[str] = None
    status: str
    submitted_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SubmissionVersionInfo(BaseModel):
    id: int
    version: int
    content: str
    attachment_name: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ========== 作业统计 ==========
class AssignmentStats(BaseModel):
    assignment_id: int
    title: str
    total_students: int
    submitted_count: int
    graded_count: int
    not_submitted: list[dict]  # [{user_id, name, student_no}]


# ========== 通知 ==========
class NotificationInfo(BaseModel):
    id: int
    user_id: int
    type: str
    title: str
    content: str
    ref_type: Optional[str] = None
    ref_id: Optional[int] = None
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    total: int
    items: list[NotificationInfo]
    unread_count: int
