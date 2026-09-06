from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.ai.business_skills.service import BusinessSkillService
from backend.app.api.deps import get_current_user
from backend.app.core.database import get_db


router = APIRouter()


class CompetitionRecommendRequest(BaseModel):
    query: str = Field(default="", max_length=2000)
    tags: list[str] = Field(default_factory=list)
    source: str | None = Field(default=None, max_length=200)
    limit: int = Field(default=5, ge=1, le=10)


class MentorMatchRequest(BaseModel):
    project_description: str = Field(..., max_length=4000)
    tag: str | None = Field(default=None, max_length=100)
    teacher_name: str | None = Field(default=None, max_length=100)
    limit: int = Field(default=5, ge=1, le=10)


def _business_response(result: dict[str, Any]) -> dict[str, Any]:
    data = dict(result["data"])
    data["response"] = result["response"]
    data["skill_name"] = result["skill_name"]
    return data


@router.post("/competition-recommend")
async def competition_recommend(
    form: CompetitionRecommendRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    parts = [form.query, f"limit={form.limit}"]
    if form.tags:
        parts.append("tags=" + ",".join(form.tags))
    if form.source:
        parts.append("source=" + form.source)
    result = await BusinessSkillService.execute(
        "competition_recommend", " ".join(parts), current_user, db
    )
    return _business_response(result)


@router.post("/mentor-match")
async def mentor_match(
    form: MentorMatchRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    parts = [form.project_description, f"limit={form.limit}"]
    if form.tag:
        parts.append("tag=" + form.tag)
    if form.teacher_name:
        parts.append("teacher_name=" + form.teacher_name)
    result = await BusinessSkillService.execute("mentor_match", " ".join(parts), current_user, db)
    return _business_response(result)
