from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from fastapi import Depends, Header
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.deps import get_current_user
from backend.app.core.config import settings
from backend.app.core.database import Base, get_db, local_now
from backend.app.models.party import PartyActivity
from backend.app.models.user import User
from backend.app.services.party_activity_service import PartyActivityService


@pytest.fixture()
def league_client():
    from backend.app import main as main_mod
    from backend.app.core import database as db_mod

    previous_engine, previous_local = db_mod.engine, db_mod.SessionLocal
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    db_mod.engine = engine
    db_mod.SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    with db_mod.SessionLocal() as db:
        users = [
            User(student_no="league", name="团员", password_hash="x", role="student", status="active", political_status="共青团员"),
            User(student_no="mass", name="群众", password_hash="x", role="student", status="active", political_status="群众"),
            User(student_no="party", name="党员", password_hash="x", role="student", status="active", political_status="中共党员"),
            User(student_no="admin", name="管理员", password_hash="x", role="admin", status="active"),
        ]
        db.add_all(users)
        db.commit()
    app = main_mod.create_app()

    def override_db():
        with db_mod.SessionLocal() as db:
            yield db

    def override_user(x_test_user: str = Header("mass"), db: Session = Depends(get_db)) -> User:
        return db.query(User).filter(User.student_no == x_test_user).one()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    try:
        with TestClient(app) as client:
            yield client, db_mod.SessionLocal
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
        db_mod.engine, db_mod.SessionLocal = previous_engine, previous_local


def _payload(**overrides):
    now = local_now()
    value = {
        "title": "主题团日",
        "category": "主题团日",
        "content": "团学活动",
        "location": "教室",
        "start_at": (now + timedelta(days=2)).isoformat(),
        "end_at": (now + timedelta(days=2, hours=1)).isoformat(),
        "registration_deadline": (now + timedelta(days=1)).isoformat(),
        "target_roles": "全体团员",
    }
    value.update(overrides)
    return value


def test_league_enums_and_political_visibility(league_client):
    client, sessions = league_client
    created = client.post("/api/v1/party/activities", json=_payload(), headers={"X-Test-User": "admin"})
    assert created.status_code == 200, created.text
    activity_id = created.json()["id"]
    assert client.post(f"/api/v1/party/activities/{activity_id}/publish", headers={"X-Test-User": "admin"}).status_code == 200
    assert client.get("/api/v1/party/activities", headers={"X-Test-User": "league"}).json()["total"] == 1
    assert client.get("/api/v1/party/activities", headers={"X-Test-User": "mass"}).json()["total"] == 0
    assert client.post(f"/api/v1/party/activities/{activity_id}/register", headers={"X-Test-User": "mass"}).status_code == 403
    assert client.post(f"/api/v1/party/activities/{activity_id}/register", headers={"X-Test-User": "league"}).status_code == 200


def test_public_activity_visible_to_mass_and_league(league_client):
    client, _ = league_client
    created = client.post("/api/v1/party/activities", json=_payload(target_roles="全体学生"), headers={"X-Test-User": "admin"})
    activity_id = created.json()["id"]
    client.post(f"/api/v1/party/activities/{activity_id}/publish", headers={"X-Test-User": "admin"})
    for user in ("mass", "league"):
        assert client.get("/api/v1/party/activities", headers={"X-Test-User": user}).json()["total"] == 1


def test_target_role_helper_rejects_unknown_user_role(league_client):
    _, sessions = league_client
    with sessions() as db:
        activity = PartyActivity(
            title="群众活动", category="群众", content="x", location="x",
            start_at=local_now(), end_at=local_now() + timedelta(hours=1),
            target_roles="群众", status="published", created_by=1,
        )
        db.add(activity)
        db.flush()
        assert PartyActivityService.is_visible(activity, db.query(User).filter_by(student_no="mass").one())


def test_frontend_enums_include_league_values():
    root = Path(__file__).parents[2]
    for relative in ("frontend/js/views/party.js", "frontend/js/admin_party.js"):
        source = (root / relative).read_text(encoding="utf-8")
        assert "主题团日" in source
        assert "团学实践" in source
        assert "团组织建设" in source
        assert "其他团学" in source
    admin_source = (root / "frontend/js/admin_party.js").read_text(encoding="utf-8")
    assert "全体团员" in admin_source
    assert "党员与团员" in admin_source
    assert "群众" in admin_source
