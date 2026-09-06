from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import Depends, Header
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.deps import get_current_user
from backend.app.core.database import Base, get_db
from backend.app.core.config import settings
from backend.app.models.party import PoliticalLearningMaterial
from backend.app.models.user import User


@pytest.fixture()
def material_client():
    from backend.app import main as main_mod
    from backend.app.core import database as db_mod

    previous_engine, previous_local = db_mod.engine, db_mod.SessionLocal
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    db_mod.engine = engine
    db_mod.SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    with db_mod.SessionLocal() as db:
        db.add_all(
            [
                User(
                    student_no="league",
                    name="团员",
                    password_hash="x",
                    role="student",
                    status="active",
                    political_status="共青团员",
                ),
                User(
                    student_no="mass",
                    name="群众",
                    password_hash="x",
                    role="student",
                    status="active",
                    political_status="群众",
                ),
                User(
                    student_no="teacher",
                    name="教师",
                    password_hash="x",
                    role="teacher",
                    status="active",
                ),
                User(
                    student_no="admin",
                    name="管理员",
                    password_hash="x",
                    role="admin",
                    status="active",
                ),
            ]
        )
        db.commit()
    app = main_mod.create_app()

    def override_db():
        with db_mod.SessionLocal() as db:
            yield db

    def override_user(
        x_test_user: str = Header("mass"), db: Session = Depends(get_db)
    ) -> User:
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


def _create(client: TestClient, **overrides) -> dict:
    body = {
        "title": "团员学习材料",
        "description": "政治学习",
        "applicable_roles": ["共青团员"],
        "target_user_ids": [],
        "status": "published",
    }
    body.update(overrides)
    response = client.post(
        "/api/v1/party/learning-materials",
        json=body,
        headers={"X-Test-User": "admin"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_political_material_visibility_and_admin_crud(material_client) -> None:
    client, _ = material_client
    league = _create(client)
    public = _create(
        client,
        title="公开材料",
        applicable_roles=["全体学生"],
    )
    assert client.post(
        "/api/v1/party/learning-materials",
        json={"title": "x", "applicable_roles": [], "status": "draft"},
        headers={"X-Test-User": "mass"},
    ).status_code == 403

    assert {item["id"] for item in client.get(
        "/api/v1/party/learning-materials", headers={"X-Test-User": "league"}
    ).json()["items"]} == {league["id"], public["id"]}
    assert {item["id"] for item in client.get(
        "/api/v1/party/learning-materials", headers={"X-Test-User": "mass"}
    ).json()["items"]} == {public["id"]}
    assert {item["id"] for item in client.get(
        "/api/v1/party/learning-materials", headers={"X-Test-User": "teacher"}
    ).json()["items"]} == {public["id"]}

    assert client.delete(
        f"/api/v1/party/learning-materials/{league['id']}",
        headers={"X-Test-User": "admin"},
    ).status_code == 200
    assert client.get(
        "/api/v1/party/learning-materials", headers={"X-Test-User": "league"}
    ).json()["total"] == 1


def test_specific_material_attachment_stays_out_of_knowledge_base(
    material_client, tmp_path, monkeypatch
) -> None:
    client, sessions = material_client
    monkeypatch.setattr(settings, "STORAGE_PATH", str(tmp_path))
    with sessions() as db:
        target = db.query(User).filter(User.student_no == "mass").one()
    item = _create(
        client,
        title="指定材料",
        applicable_roles=["指定人员"],
        target_user_ids=[target.id],
    )
    with patch(
        "backend.app.services.party_political_material_service.PartyKnowledgeAdapter.ingest_political_material"
    ) as ingest:
        response = client.post(
            f"/api/v1/party/learning-materials/{item['id']}/attachments",
            files={"file": ("secret.pdf", b"test", "application/pdf")},
            headers={"X-Test-User": "admin"},
        )
    assert response.status_code == 200, response.text
    attachment = response.json()["attachments"][0]
    assert attachment["original_name"] == "secret.pdf"
    ingest.assert_not_called()
    assert client.get(
        "/api/v1/party/learning-materials", headers={"X-Test-User": "mass"}
    ).json()["total"] == 1
    assert client.get(
        "/api/v1/party/learning-materials", headers={"X-Test-User": "league"}
    ).json()["total"] == 0
    download_url = (
        f"/api/v1/party/learning-materials/{item['id']}"
        f"/attachments/{attachment['file_id']}"
    )
    allowed = client.get(download_url, headers={"X-Test-User": "mass"})
    assert allowed.status_code == 200
    assert allowed.content == b"test"
    assert "attachment" in allowed.headers["content-disposition"]
    assert client.get(
        download_url, headers={"X-Test-User": "league"}
    ).status_code == 404
    assert client.get(
        download_url, headers={"X-Test-User": "admin"}
    ).status_code == 200
    with sessions() as db:
        assert db.get(PoliticalLearningMaterial, item["id"]).attachments
