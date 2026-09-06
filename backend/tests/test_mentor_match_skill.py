import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.ai.business_skills.mentor_match import MentorMatchExecutor
from backend.app.core.database import Base
from backend.app.main import app
from backend.app.models.user import User
from backend.app.repositories.teacher_repo import TeacherRepository
from backend.app.services.semantic_service import SemanticService


class FakeModel:
    def encode(self, texts, **kwargs):
        return [[1.0, 0.0] if any(key in text for key in ("大语言模型", "自然语言", "NLP")) else [0.0, 1.0] for text in texts]


@pytest.fixture()
def skill_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    SemanticService._model = FakeModel()
    SemanticService._model_failed = False
    try:
        yield db
    finally:
        db.close()
        engine.dispose()
        SemanticService.reset_model()


def _user(db, student_no, name, role="student", status="active"):
    user = User(
        student_no=student_no,
        name=name,
        password_hash="hash",
        role=role,
        status=status,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_mentor_short_description_guides_user(skill_db):
    student = _user(skill_db, "S-M5", "学生")
    result = asyncio.run(MentorMatchExecutor().execute("做一个摘要系统", student, skill_db))
    assert result["needs_more_input"] is True
    assert result["items"] == []
    assert "至少 20" in result["message"]


def test_mentor_matches_active_direction_and_returns_reason(skill_db):
    student = _user(skill_db, "S-M5", "学生")
    teacher = _user(skill_db, "T-M5", "张老师", role="teacher")
    disabled_teacher = _user(skill_db, "T-OFF", "停用老师", role="teacher", status="disabled")
    direction = TeacherRepository.create_direction(
        skill_db,
        teacher.id,
        title="自然语言处理与大语言模型",
        description="研究自动摘要和文本生成",
        tags_json='["NLP", "机器学习"]',
    )
    TeacherRepository.create_direction(
        skill_db,
        disabled_teacher.id,
        title="自然语言处理",
        tags_json='["NLP"]',
    )

    description = "我想开发一个基于大语言模型的自动论文摘要系统，并研究自然语言生成质量"
    result = asyncio.run(MentorMatchExecutor().execute(description, student, skill_db))

    assert result["needs_more_input"] is False
    assert result["total"] == 1
    assert result["items"][0]["teacher_id"] == teacher.id
    assert result["items"][0]["direction_id"] == direction.id
    assert result["items"][0]["title"] == direction.title
    assert "推荐理由" in result["items"][0]["reason"]
    assert "student_no" not in result["items"][0]


def test_mentor_fallback_and_endpoint_permission(skill_db):
    student = _user(skill_db, "S-M5", "学生")
    teacher = _user(skill_db, "T-M5", "李老师", role="teacher")
    TeacherRepository.create_direction(
        skill_db,
        teacher.id,
        title="NLP 自动摘要",
        description="自然语言处理",
    )
    SemanticService._model = None
    SemanticService._model_failed = True
    result = asyncio.run(
        MentorMatchExecutor().execute(
            "计划研究自然语言处理技术并完成一个自动文本摘要平台", student, skill_db
        )
    )
    assert result["total"] == 1

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/skills/business/mentor-match",
            json={"project_description": "足够长的项目描述用于接口权限测试"},
        )
    assert response.status_code == 401
