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
from backend.app.core.database import Base, get_db, local_now
from backend.app.models.achievement import Achievement
from backend.app.models.user import User
from backend.app.services.achievement_templates import ACHIEVEMENT_TEMPLATES


@pytest.fixture()
def stats_client(tmp_path: Path):
    from backend.app.core import config as cfg
    from backend.app.core import database as db_mod

    previous_values = {
        "DB_URL": cfg.settings.DB_URL,
        "ENV": cfg.settings.ENV,
        "API_RATE_LIMIT": cfg.settings.API_RATE_LIMIT,
        "STORAGE_PATH": cfg.settings.STORAGE_PATH,
        "CLASS_NAME": cfg.settings.CLASS_NAME,
    }
    cfg.settings.DB_URL = "sqlite:///:memory:"
    cfg.settings.ENV = "test"
    cfg.settings.API_RATE_LIMIT = 100000
    cfg.settings.STORAGE_PATH = str(tmp_path / "storage")
    cfg.settings.CLASS_NAME = "许国志大数据英才班"

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
                User(student_no="s2", name="学生二", password_hash="unused", role="student", status="active"),
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


def _achievement(user_id: int, category: str, status: str, *, deleted: bool = False) -> Achievement:
    return Achievement(
        user_id=user_id,
        category=category,
        title=f"{category}-{status}",
        status=status,
        deleted_at=local_now() if deleted else None,
    )


def test_stats_return_all_categories_and_only_count_approved_active_records(stats_client):
    client, session_factory = stats_client
    with session_factory() as db:
        users = {user.student_no: user.id for user in db.query(User).all()}
        db.add_all(
            [_achievement(users["s1"], category, "approved") for category in ACHIEVEMENT_TEMPLATES]
            + [
                _achievement(users["s1"], "paper", "approved"),
                _achievement(users["s1"], "award", "pending"),
                _achievement(users["s1"], "research", "rejected"),
                _achievement(users["s1"], "patent", "approved", deleted=True),
                _achievement(users["s2"], "paper", "approved"),
            ]
        )
        db.commit()

    response = client.get("/api/v1/achievements/stats")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["class_name"] == "许国志大数据英才班"
    assert list(body["counts"]) == list(ACHIEVEMENT_TEMPLATES)
    assert body["counts"] == {
        "paper": 2,
        "award": 1,
        "research": 1,
        "patent": 1,
        "innovation": 1,
        "organization": 1,
        "social": 1,
        "arts": 1,
    }
    assert body["total"] == 9


def test_stats_are_isolated_to_current_user_and_keep_zero_categories(stats_client):
    client, session_factory = stats_client
    with session_factory() as db:
        user_id = db.query(User).filter(User.student_no == "s1").one().id
        db.add(_achievement(user_id, "paper", "approved"))
        db.commit()

    response = client.get(
        "/api/v1/achievements/stats",
        headers={"X-Test-User": "s2"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["counts"] == {category: 0 for category in ACHIEVEMENT_TEMPLATES}
    assert response.json()["total"] == 0


def test_overview_statically_loads_and_renders_achievement_stats():
    source = (PROJECT_ROOT / "frontend" / "js" / "views" / "overview.js").read_text(encoding="utf-8")

    assert 'api("/api/v1/achievements/stats")' in source
    assert "Promise.allSettled(requests)" in source
    assert "用户数据概览" in source
    assert "亲爱的${className}的同学，您好!" in source
    assert "进入${className}以来，您共填报了以下数据:" in source
    for category in ACHIEVEMENT_TEMPLATES:
        assert f'achievementStatButton("{category}"' in source
    assert 'context.navigate("community", { view: "mine", category:' in source
