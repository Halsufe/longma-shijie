from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class BatchTimes(BaseModel):
    student_apply_start: datetime
    student_apply_end: datetime
    mentor_select_start: datetime
    mentor_select_end: datetime
    main_publish_at: datetime
    supplement_student_start: Optional[datetime] = None
    supplement_student_end: Optional[datetime] = None
    supplement_mentor_start: Optional[datetime] = None
    supplement_mentor_end: Optional[datetime] = None
    supplement_publish_at: Optional[datetime] = None


class BatchCreate(BatchTimes):
    name: str = Field(..., min_length=1, max_length=200)
    academic_year: str = Field(..., min_length=1, max_length=20)
    term: str = Field(..., min_length=1, max_length=20)


class BatchUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    academic_year: Optional[str] = Field(None, min_length=1, max_length=20)
    term: Optional[str] = Field(None, min_length=1, max_length=20)
    expected_version: Optional[int] = Field(None, ge=1)
    student_apply_start: Optional[datetime] = None
    student_apply_end: Optional[datetime] = None
    mentor_select_start: Optional[datetime] = None
    mentor_select_end: Optional[datetime] = None
    main_publish_at: Optional[datetime] = None
    supplement_student_start: Optional[datetime] = None
    supplement_student_end: Optional[datetime] = None
    supplement_mentor_start: Optional[datetime] = None
    supplement_mentor_end: Optional[datetime] = None
    supplement_publish_at: Optional[datetime] = None


class StudentRosterRow(BaseModel):
    student_no: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    class_name: str = Field(..., min_length=1, max_length=100)


class MentorRosterUpdate(BaseModel):
    teacher_ids: list[int] = Field(..., min_length=3)


class PreferenceItemInput(BaseModel):
    teacher_id: int
    rank: int = Field(..., ge=1)
    reason: str = ""


class PreferenceInput(BaseModel):
    round: str = "main"
    personal_statement: str = ""
    items: list[PreferenceItemInput] = Field(default_factory=list)
    submit: bool = False

    @model_validator(mode="after")
    def validate_round(self):
        if self.round not in {"main", "supplement"}:
            raise ValueError("round 必须为 main 或 supplement")
        return self


class DecisionItemInput(BaseModel):
    student_id: int
    decision: str


class DecisionInput(BaseModel):
    round: str = "main"
    items: list[DecisionItemInput] = Field(default_factory=list)
    submit: bool = False


class ReopenRequest(BaseModel):
    stage: str = Field(..., pattern="^(student|mentor)$")


class ExtendRequest(BaseModel):
    stage: str = Field(..., pattern="^(student|mentor|supplement_student|supplement_mentor)$")
    new_end: datetime


class AdvanceRequest(BaseModel):
    """Explicit acknowledgement for an administrator-controlled phase transition."""
    confirm: bool = True


class ImportConfirm(BaseModel):
    rows: list[StudentRosterRow]
    token: Optional[str] = None
