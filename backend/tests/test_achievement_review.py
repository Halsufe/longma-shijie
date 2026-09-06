from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import Depends, Header
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.api.deps import get_current_user
from backend.app.core.database import Base, get_db
from backend.app.models.achievement import Achievement
from backend.app.models.user import User
from backend.app.services.achievement_templates import ACHIEVEMENT_TEMPLATES


@pytest.fixture()
def review_client(tmp_path: Path):
    from backend.app.core import config as cfg
    from backend.app.core import database as db_mod

    previous_values = {
        "DB_URL": cfg.settings.DB_URL,
        "ENV": cfg.settings.ENV,
        "API_RATE_LIMIT": cfg.settings.API_RATE_LIMIT,
        "STORAGE_PATH": cfg.settings.STORAGE_PATH,
    }
    cfg.settings.DB_URL = "sqlite:///:memory:"
    cfg.settings.ENV = "test"
    cfg.settings.API_RATE_LIMIT = 100000
    cfg.settings.STORAGE_PATH = str(tmp_path / "storage")

    db_mod.engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    db_mod.SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=db_mod.engine,
        future=True,
    )

    from backend.app.main import create_app

    app = create_app()
    Base.metadata.create_all(bind=db_mod.engine)
    with db_mod.SessionLocal() as db:
        db.add_all(
            [
                User(student_no="s1", name="学生一", password_hash="unused", role="student", status="active"),
                User(student_no="admin", name="管理员", password_hash="unused", role="admin", status="active"),
            ]
        )
        db.commit()

    def override_get_db():
        session = db_mod.SessionLocal()
        try:
            yield session
        finally:
            session.close()

    def override_current_user(
        x_test_user: str = Header("s1"),
        db: Session = Depends(get_db),
    ) -> User:
        return db.query(User).filter(User.student_no == x_test_user).one()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    with TestClient(app) as client:
        yield client, db_mod.SessionLocal

    app.dependency_overrides.clear()
    for name, value in previous_values.items():
        setattr(cfg.settings, name, value)


def _seed_achievement(
    session_factory,
    *,
    category: str = "award",
    title: str = "全国案例竞赛",
    status: str = "pending",
) -> int:
    details = {
        "award_grade": "一等奖",
        "organizer": "示例主办单位",
        "award_year": 2026,
        "award_month": 6,
        "teacher_names": "王老师",
        "is_team": "是",
        "is_leader": "是",
        "member_names": "张三, 李四",
        "description": "竞赛成果说明",
    }
    if category != "award":
        details = {field.key: f"值-{field.key}" for field in ACHIEVEMENT_TEMPLATES[category].fields}

    with session_factory() as db:
        user_id = db.query(User).filter(User.student_no == "s1").one().id
        achievement = Achievement(
            user_id=user_id,
            category=category,
            title=title,
            level="国家级" if category == "award" else None,
            achievement_date="2026-06",
            status=status,
            is_public=True,
        )
        achievement.details = details
        achievement.proofs = [
            {
                "id": "proof.pdf",
                "stored_name": "proof.pdf",
                "name": "获奖证书.pdf",
                "size": 128,
                "mime": "application/pdf",
            }
        ]
        db.add(achievement)
        db.commit()
        db.refresh(achievement)
        return achievement.id


def test_admin_list_returns_review_summary_and_keeps_filters(review_client):
    client, session_factory = review_client
    achievement_id = _seed_achievement(session_factory)
    _seed_achievement(session_factory, title="不匹配标题", status="rejected")

    forbidden = client.get("/api/v1/achievements/admin/all")
    assert forbidden.status_code == 403

    response = client.get(
        "/api/v1/achievements/admin/all?status=pending&q=案例&page_size=100",
        headers={"X-Test-User": "admin"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["id"] == achievement_id
    assert item["details_summary"] == {
        "award_grade": "一等奖",
        "organizer": "示例主办单位",
        "award_year": 2026,
        "award_month": 6,
    }
    assert item["proof_count"] == 1
    assert item["level"] == "国家级"
    assert item["year"] == 2026


def test_admin_detail_and_pending_only_review_state_machine(review_client):
    client, session_factory = review_client
    achievement_id = _seed_achievement(session_factory)
    admin_headers = {"X-Test-User": "admin"}

    detail = client.get(f"/api/v1/achievements/{achievement_id}", headers=admin_headers)
    assert detail.status_code == 200
    assert detail.json()["details"]["award_grade"] == "一等奖"
    assert detail.json()["proofs"][0]["name"] == "获奖证书.pdf"

    approved = client.put(
        f"/api/v1/achievements/admin/{achievement_id}/approve",
        headers=admin_headers,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert approved.json()["details"]["award_grade"] == "一等奖"
    assert approved.json()["proofs"][0]["name"] == "获奖证书.pdf"

    duplicate = client.put(
        f"/api/v1/achievements/admin/{achievement_id}/reject",
        headers=admin_headers,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "ACHIEVEMENT_REVIEW_CONFLICT"
    assert "仅待审核成果" in duplicate.json()["error"]["message"]


def test_review_status_updates_approved_only_statistics(review_client):
    client, session_factory = review_client
    approved_id = _seed_achievement(session_factory, title="待通过成果")
    rejected_id = _seed_achievement(session_factory, title="待拒绝成果")
    admin_headers = {"X-Test-User": "admin"}

    assert client.get("/api/v1/achievements/stats").json()["total"] == 0
    assert client.put(
        f"/api/v1/achievements/admin/{approved_id}/approve",
        headers=admin_headers,
    ).status_code == 200
    assert client.put(
        f"/api/v1/achievements/admin/{rejected_id}/reject",
        headers=admin_headers,
    ).status_code == 200

    stats = client.get("/api/v1/achievements/stats").json()
    assert stats["counts"]["award"] == 1
    assert stats["total"] == 1


def test_admin_frontend_reuses_templates_escapes_values_and_exposes_proof_actions():
    source = (PROJECT_ROOT / "frontend" / "js" / "views" / "admin.js").read_text(encoding="utf-8")

    assert 'getAchievementTemplate(item.category)' in source
    assert "escapeHtml(field.label)" in source
    assert "escapeHtml(detailValue(details[field.key]))" in source
    assert "data-proof-preview" in source
    assert "data-proof-download" in source
