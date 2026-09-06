import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.ai.business_skills.competition_recommend import CompetitionRecommendExecutor
from backend.app.api.deps import get_current_user
from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.app.models.user import User
from backend.app.repositories.resource_repo import ResourceRepository
from backend.app.services.semantic_service import SemanticService


class FakeModel:
    def encode(self, texts, **kwargs):
        return [[1.0, 0.0] if "机器学习" in text else [0.0, 1.0] for text in texts]


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


def _student(db):
    user = User(
        student_no="S-M4",
        name="学生",
        password_hash="hash",
        role="student",
        status="active",
    )
    user.profile = {"major": "数据科学", "skills": ["机器学习"]}
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_competition_profile_match_filters_deadline_and_adds_reason(skill_db):
    user = _student(skill_db)
    future = datetime.now(timezone.utc) + timedelta(days=30)
    expired = datetime.now(timezone.utc) - timedelta(days=1)
    matched = ResourceRepository.create(
        skill_db,
        user.id,
        type="competition",
        title="机器学习挑战赛",
        content="人工智能数据建模",
        tags_json='["机器学习", "人工智能"]',
        source="学会",
        deadline=future,
        status="approved",
    )
    ResourceRepository.create(
        skill_db,
        user.id,
        type="competition",
        title="过期机器学习竞赛",
        tags_json='["机器学习"]',
        deadline=expired,
        status="approved",
    )
    ResourceRepository.create(
        skill_db,
        user.id,
        type="competition",
        title="待审核竞赛",
        status="pending",
    )

    result = asyncio.run(CompetitionRecommendExecutor().execute("想参加人工智能比赛 limit=5", user, skill_db))

    assert result["total"] == 1
    assert result["items"][0]["id"] == matched.id
    assert "推荐理由" in result["items"][0]["reason"]
    assert result["items"][0]["deadline"] is not None


def test_competition_fallback_uses_heat_and_limit(skill_db):
    user = _student(skill_db)
    hot = ResourceRepository.create(
        skill_db,
        user.id,
        type="competition",
        title="热门综合赛",
        status="approved",
        view_count=100,
    )
    ResourceRepository.create(
        skill_db,
        user.id,
        type="competition",
        title="普通综合赛",
        status="approved",
        view_count=1,
    )
    SemanticService._model = None
    SemanticService._model_failed = True

    result = asyncio.run(CompetitionRecommendExecutor().execute("前1个", user, skill_db))
    assert result["total"] == 1
    assert result["items"][0]["id"] == hot.id


def test_competition_endpoint_requires_login(skill_db):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/skills/business/competition-recommend",
            json={"query": "机器学习"},
        )
    assert response.status_code == 401

