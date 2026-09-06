from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from alembic import command
from alembic.config import Config
from fastapi import Depends, Header
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.deps import get_current_user
from backend.app.core.config import settings
from backend.app.core.database import Base, get_db
from backend.app.models.audit import AuditLog
from backend.app.models.party import PoliticalStatusReview
from backend.app.models.notification import Notification
from backend.app.models.user import User
from backend.app.services.party_notify_adapter import PartyNotifyAdapter


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_REVISION = "j1234f5a6b7c"
POLITICAL_REVISION = "k2345g6h7i8j"


def _alembic_config(database_url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _party(party_type: str, **overrides) -> dict:
    value = {
        "party_type": party_type,
        "branch_name": "大数据党支部",
        "class_name": "测试25级",
        "grade": "25",
        "apply_date": "2024-01",
        "apply_status": "递交申请",
    }
    value.update(overrides)
    return value


def test_e7_migration_backfills_and_downgrades_without_losing_legacy_data(
    tmp_path: Path, monkeypatch
) -> None:
    database_path = tmp_path / "political-migration.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("DB_URL", database_url)
    config = _alembic_config(database_url)
    command.upgrade(config, BASE_REVISION)

    engine = create_engine(database_url, future=True)
    rows = [
        ("formal", "正式党员", None),
        ("probation", "预备党员", None),
        ("activist", "入党积极分子", None),
        ("plain", None, None),
        ("invalid", None, "not-json"),
    ]
    with engine.begin() as connection:
        for index, (student_no, party_type, raw_json) in enumerate(rows, start=1):
            if raw_json is None:
                party_json = (
                    json.dumps({"party_type": party_type}, ensure_ascii=False)
                    if party_type
                    else "{}"
                )
            else:
                party_json = raw_json
            connection.execute(
                text(
                    "INSERT INTO users (id, student_no, name, password_hash, role, "
                    "status, party_json, created_at, updated_at) VALUES "
                    "(:id, :student_no, :name, 'hash', 'student', 'active', "
                    ":party_json, '2026-01-01', '2026-01-01')"
                ),
                {
                    "id": index,
                    "student_no": student_no,
                    "name": student_no,
                    "party_json": party_json,
                },
            )

    command.upgrade(config, POLITICAL_REVISION)
    inspector = inspect(engine)
    columns = {item["name"] for item in inspector.get_columns("users")}
    assert {"political_status", "political_status_updated_at"} <= columns
    assert {"political_status_reviews", "political_materials"} <= set(
        inspector.get_table_names()
    )
    assert {
        item["name"] for item in inspector.get_indexes("political_status_reviews")
    } == {"ix_political_review_status_submitted", "ix_political_review_user"}

    with engine.connect() as connection:
        statuses = dict(
            connection.execute(
                text("SELECT student_no, political_status FROM users")
            ).all()
        )
        assert statuses == {
            "formal": "中共党员",
            "probation": "预备党员",
            "activist": "入党积极分子",
            "plain": "群众",
            "invalid": "群众",
        }
        assert connection.execute(
            text(
                "SELECT count(*) FROM users "
                "WHERE political_status_updated_at IS NOT NULL"
            )
        ).scalar_one() == 5
        assert connection.execute(
            text(
                "SELECT count(*) FROM audit_logs "
                "WHERE action='political_status_initialize'"
            )
        ).scalar_one() == 5

    command.downgrade(config, BASE_REVISION)
    inspector = inspect(engine)
    assert "political_status" not in {
        item["name"] for item in inspector.get_columns("users")
    }
    assert "political_status_reviews" not in inspector.get_table_names()
    assert "political_materials" not in inspector.get_table_names()
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM users")).scalar_one() == 5
        assert connection.execute(
            text(
                "SELECT party_json FROM users WHERE student_no='formal'"
            )
        ).scalar_one() == json.dumps({"party_type": "正式党员"}, ensure_ascii=False)
        assert connection.execute(
            text(
                "SELECT count(*) FROM audit_logs "
                "WHERE action='political_status_initialize'"
            )
        ).scalar_one() == 0


@pytest.fixture()
def political_client(tmp_path: Path):
    from backend.app import main as main_mod
    from backend.app.core import database as db_mod

    previous_engine = db_mod.engine
    previous_session = db_mod.SessionLocal
    previous_main_engine = main_mod.engine
    previous_storage = settings.STORAGE_PATH
    previous_env = settings.ENV
    previous_rate_limit = settings.API_RATE_LIMIT
    previous_classes = settings.PARTY_CLASSES

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    db_mod.engine = engine
    db_mod.SessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine, future=True
    )
    main_mod.engine = engine
    settings.STORAGE_PATH = str(tmp_path / "storage")
    settings.ENV = "test"
    settings.API_RATE_LIMIT = 100000
    settings.PARTY_CLASSES = "测试25级"
    Base.metadata.create_all(bind=engine)
    with db_mod.SessionLocal() as db:
        db.add_all(
            [
                User(
                    student_no="student",
                    name="普通学生",
                    password_hash="unused",
                    role="student",
                    status="active",
                ),
                User(
                    student_no="student2",
                    name="学生二",
                    password_hash="unused",
                    role="student",
                    status="active",
                ),
                User(
                    student_no="party",
                    name="党员学生",
                    password_hash="unused",
                    role="student",
                    status="active",
                ),
                User(
                    student_no="teacher",
                    name="教师",
                    password_hash="unused",
                    role="teacher",
                    status="active",
                ),
                User(
                    student_no="admin",
                    name="管理员",
                    password_hash="unused",
                    role="admin",
                    status="active",
                ),
            ]
        )
        db.commit()

    app = main_mod.create_app()

    def override_db():
        session = db_mod.SessionLocal()
        try:
            yield session
        finally:
            session.close()

    def override_user(
        x_test_user: str = Header("student"),
        db: Session = Depends(get_db),
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
        db_mod.engine = previous_engine
        db_mod.SessionLocal = previous_session
        main_mod.engine = previous_main_engine
        settings.STORAGE_PATH = previous_storage
        settings.ENV = previous_env
        settings.API_RATE_LIMIT = previous_rate_limit
        settings.PARTY_CLASSES = previous_classes


def _headers(user: str) -> dict[str, str]:
    return {"X-Test-User": user}


def _user_id(session_factory, student_no: str) -> int:
    with session_factory() as db:
        return db.query(User.id).filter(User.student_no == student_no).scalar()


def test_student_apply_mine_validation_and_permissions(political_client) -> None:
    client, _ = political_client
    mine = client.get(
        "/api/v1/party/political-status/mine", headers=_headers("student")
    )
    assert mine.status_code == 200
    assert mine.json() == {
        "political_status": "群众",
        "political_status_updated_at": None,
        "latest_review": None,
    }

    applied = client.post(
        "/api/v1/party/political-status/mine",
        json={"to_status": "共青团员", "remark": "入团材料齐全"},
        headers=_headers("student"),
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["status"] == "pending"
    assert applied.json()["from_status"] == "群众"

    duplicate = client.post(
        "/api/v1/party/political-status/mine",
        json={"to_status": "共青团员"},
        headers=_headers("student"),
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "POLITICAL_STATUS_REVIEW_PENDING"

    direct_party = client.post(
        "/api/v1/party/political-status/mine",
        json={"to_status": "中共党员"},
        headers=_headers("student2"),
    )
    assert direct_party.status_code == 422
    teacher = client.get(
        "/api/v1/party/political-status/mine", headers=_headers("teacher")
    )
    assert teacher.status_code == 403
    assert client.get(
        "/api/v1/party/political-status/reviews", headers=_headers("student")
    ).status_code == 403


def test_approve_is_atomic_audited_notified_and_idempotent(political_client) -> None:
    client, session_factory = political_client
    review_id = client.post(
        "/api/v1/party/political-status/mine",
        json={"to_status": "共青团员"},
        headers=_headers("student"),
    ).json()["id"]

    with patch.object(
        PartyNotifyAdapter,
        "notify_political_status_approved",
        return_value=1,
    ) as notify:
        approved = client.put(
            f"/api/v1/party/political-status/reviews/{review_id}/approve",
            json={"remark": "审核通过"},
            headers=_headers("admin"),
        )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    notify.assert_called_once()
    with session_factory() as db:
        student = db.query(User).filter(User.student_no == "student").one()
        assert student.political_status == "共青团员"
        assert student.political_status_updated_at is not None
        audit = db.query(AuditLog).filter(
            AuditLog.target_type == "political_status_review",
            AuditLog.target_id == str(review_id),
        ).one()
        assert audit.action == "political_status_approved"
        assert json.loads(audit.detail)["to_status"] == "共青团员"

    repeated = client.put(
        f"/api/v1/party/political-status/reviews/{review_id}/reject",
        json={},
        headers=_headers("admin"),
    )
    assert repeated.status_code == 409
    assert repeated.json()["error"]["code"] == "POLITICAL_STATUS_REVIEW_COMPLETED"


def test_approval_notification_is_persisted_once(political_client) -> None:
    client, session_factory = political_client
    review_id = client.post(
        "/api/v1/party/political-status/mine",
        json={"to_status": "共青团员"},
        headers=_headers("student"),
    ).json()["id"]
    approved = client.put(
        f"/api/v1/party/political-status/reviews/{review_id}/approve",
        json={},
        headers=_headers("admin"),
    )
    assert approved.status_code == 200
    with session_factory() as db:
        student_id = db.query(User.id).filter(User.student_no == "student").scalar()
        notices = db.query(Notification).filter(
            Notification.type == "political_status_change",
            Notification.ref_type == "political_status_review",
            Notification.ref_id == review_id,
        ).all()
        assert len(notices) == 1
        assert notices[0].user_id == student_id


def test_reject_preserves_status_and_admin_list_filters(political_client) -> None:
    client, session_factory = political_client
    review_id = client.post(
        "/api/v1/party/political-status/mine",
        json={"to_status": "共青团员"},
        headers=_headers("student2"),
    ).json()["id"]
    rejected = client.put(
        f"/api/v1/party/political-status/reviews/{review_id}/reject",
        json={"remark": "材料不完整"},
        headers=_headers("admin"),
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    with session_factory() as db:
        student = db.query(User).filter(User.student_no == "student2").one()
        assert student.political_status == "群众"
        assert student.political_status_updated_at is None

    listed = client.get(
        "/api/v1/party/political-status/reviews?status=rejected&to_status=共青团员",
        headers=_headers("admin"),
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["remark"] == "材料不完整"


def test_admin_political_roster_covers_all_students_and_filters_status(
    political_client,
) -> None:
    client, session_factory = political_client
    with session_factory() as db:
        db.query(User).filter(User.student_no == "student2").update(
            {"political_status": "共青团员"}
        )
        db.query(User).filter(User.student_no == "party").update(
            {"political_status": "中共党员"}
        )
        db.commit()

    listed = client.get(
        "/api/v1/party/political-status/roster",
        headers=_headers("admin"),
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 3
    assert {
        item["political_status"] for item in listed.json()["items"]
    } == {"中共党员", "共青团员", "群众"}

    filtered = client.get(
        "/api/v1/party/political-status/roster?political_status=共青团员",
        headers=_headers("admin"),
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["student_no"] == "student2"

    forbidden = client.get(
        "/api/v1/party/political-status/roster",
        headers=_headers("student"),
    )
    assert forbidden.status_code == 403


def test_party_profile_create_and_status_changes_sync_without_reviews(
    political_client,
) -> None:
    client, session_factory = political_client
    user_id = _user_id(session_factory, "party")
    created = client.post(
        "/api/v1/party/members",
        json={
            "user_id": user_id,
            **_party("入党积极分子"),
        },
        headers=_headers("admin"),
    )
    assert created.status_code == 200, created.text
    with session_factory() as db:
        user = db.get(User, user_id)
        assert user is not None and user.political_status == "入党积极分子"
        assert db.query(PoliticalStatusReview).filter(
            PoliticalStatusReview.user_id == user_id
        ).count() == 0

    for status, date, expected in [
        ("确定为积极分子", "2024-02", "入党积极分子"),
        ("列为发展对象", "2024-03", "入党积极分子"),
        ("接受为预备党员", "2024-04", "预备党员"),
        ("转为正式党员", "2025-04", "中共党员"),
    ]:
        response = client.put(
            f"/api/v1/party/members/{user_id}/status",
            json={"apply_status": status, "effective_date": date},
            headers=_headers("admin"),
        )
        assert response.status_code == 200, response.text
        with session_factory() as db:
            user = db.get(User, user_id)
            assert user is not None and user.political_status == expected
            assert db.query(PoliticalStatusReview).filter(
                PoliticalStatusReview.user_id == user_id
            ).count() == 0


def test_new_static_routes_are_registered_before_activity_dynamic_routes(
    political_client,
) -> None:
    from backend.app.api.routes.party import router

    paths = [route.path for route in router.routes]
    mine_index = paths.index("/political-status/mine")
    review_index = paths.index("/political-status/reviews")
    activity_dynamic = paths.index("/activities/{activity_id}")
    assert mine_index < activity_dynamic
    assert review_index < activity_dynamic
