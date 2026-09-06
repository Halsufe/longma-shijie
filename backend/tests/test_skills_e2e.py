from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.deps import get_current_user
from backend.app.core.config import settings
from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.app.models.user import User
from backend.app.repositories.resource_repo import ResourceRepository
from backend.app.repositories.skill_repo import SkillRepository
from backend.app.services.achievement_files import AchievementFileService
from backend.app.services.semantic_service import SemanticService


class FakeModel:
    def encode(self, texts, **kwargs):
        return [[1.0, 0.0] if "机器学习" in text else [0.0, 1.0] for text in texts]


@pytest.fixture()
def e2e_client(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    db = session_factory()
    user = User(
        student_no="E2E",
        name="端到端学生",
        password_hash="hash",
        role="student",
        status="active",
    )
    user.profile = {"skills": ["机器学习"]}
    db.add(user)
    db.commit()
    db.refresh(user)
    SkillRepository.seed_system_skills(db)

    def override_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def override_user():
        session = session_factory()
        try:
            return session.query(User).filter(User.id == user.id).one()
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    monkeypatch.setattr(AchievementFileService, "validate_owned", staticmethod(lambda *args: None))
    SemanticService._model = FakeModel()
    SemanticService._model_failed = False
    old_env = settings.ENV
    settings.ENV = "test"
    try:
        with TestClient(app) as client:
            yield client, db, user
    finally:
        settings.ENV = old_env
        app.dependency_overrides.clear()
        SemanticService.reset_model()
        db.close()
        engine.dispose()


def test_public_skills_and_competition_business_endpoint(e2e_client):
    client, db, user = e2e_client
    future = datetime.now(timezone.utc) + timedelta(days=10)
    ResourceRepository.create(
        db,
        user.id,
        type="competition",
        title="机器学习创新赛",
        tags_json='["机器学习"]',
        deadline=future,
        status="approved",
    )

    skills = client.get("/api/v1/skills")
    assert skills.status_code == 200
    business = [item for item in skills.json()["items"] if item["category"] == "business"]
    assert {item["name"] for item in business} == {
        "competition_recommend",
        "mentor_match",
        "party_query",
        "achievement_manage",
    }

    response = client.post(
        "/api/v1/skills/business/competition-recommend",
        json={"query": "机器学习", "limit": 5},
    )
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert "推荐理由" in response.json()["items"][0]["reason"]


def test_achievement_http_write_requires_matching_confirmation(e2e_client):
    client, db, user = e2e_client
    payload = {
        "category": "paper",
        "title": "兼容成果",
        "proofs": [{"stored_name": "proof.pdf", "name": "proof.pdf", "size": 10}],
    }
    denied = client.post(
        "/api/v1/achievements",
        json=payload,
        headers={"X-AI-Skill": "achievement_manage"},
    )
    assert denied.status_code == 400
    assert denied.json()["error"]["code"] == "CONFIRMATION_REQUIRED"

    preview = client.post(
        "/api/v1/confirm/preview",
        json={"operation": "achievement.create", "data": payload},
    )
    assert preview.status_code == 200, preview.text
    confirmed = client.post(
        "/api/v1/achievements",
        json={**payload, "confirmation_token": preview.json()["confirmation_token"]},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "pending"

    changed = client.post(
        "/api/v1/achievements",
        json={**payload, "title": "篡改标题", "confirmation_token": preview.json()["confirmation_token"]},
    )
    assert changed.status_code == 400
    assert changed.json()["error"]["code"] == "CONFIRMATION_MISMATCH"
