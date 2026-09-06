from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import Depends, Header
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.deps import get_current_user
from backend.app.core.config import settings
from backend.app.core.database import Base, get_db, local_now
from backend.app.models.party import PartyActivity, PartyActivityParticipant
from backend.app.models.user import User


def _party(party_type: str) -> dict:
    return {
        "party_type": party_type,
        "branch_name": "大数据党支部",
        "class_name": "测试数据25级",
        "grade": "25",
        "apply_date": "2025-01",
        "apply_status": "递交申请",
    }


@pytest.fixture()
def registration_client(tmp_path: Path):
    from backend.app import main as main_mod
    from backend.app.core import database as db_mod

    previous_engine = db_mod.engine
    previous_session_local = db_mod.SessionLocal
    previous_main_engine = main_mod.engine
    previous_storage = settings.STORAGE_PATH
    previous_env = settings.ENV
    previous_rate_limit = settings.API_RATE_LIMIT
    previous_window = settings.PARTY_SIGN_IN_WINDOW_MINUTES

    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    db_mod.engine = test_engine
    db_mod.SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine,
        future=True,
    )
    main_mod.engine = test_engine
    settings.STORAGE_PATH = str(tmp_path / "storage")
    settings.ENV = "test"
    settings.API_RATE_LIMIT = 100000
    settings.PARTY_SIGN_IN_WINDOW_MINUTES = 60

    Base.metadata.create_all(bind=test_engine)
    with db_mod.SessionLocal() as db:
        users = [
            User(student_no="formal", name="正式党员", password_hash="unused", role="student", status="active"),
            User(student_no="probation", name="预备党员", password_hash="unused", role="student", status="active"),
            User(student_no="activist", name="积极分子", password_hash="unused", role="student", status="active"),
            User(student_no="plain", name="普通学生", password_hash="unused", role="student", status="active"),
            User(student_no="plain2", name="普通学生二", password_hash="unused", role="student", status="active"),
            User(student_no="teacher", name="教师", password_hash="unused", role="teacher", status="active"),
            User(student_no="alumni", name="校友", password_hash="unused", role="alumni", status="active"),
            User(student_no="admin", name="管理员", password_hash="unused", role="admin", status="active"),
        ]
        users[0].party = _party("正式党员")
        users[1].party = _party("预备党员")
        users[2].party = _party("入党积极分子")
        db.add_all(users)
        db.commit()

    app = main_mod.create_app()

    def override_get_db():
        session = db_mod.SessionLocal()
        try:
            yield session
        finally:
            session.close()

    def override_current_user(
        x_test_user: str = Header("plain"),
        db: Session = Depends(get_db),
    ) -> User:
        return db.query(User).filter(User.student_no == x_test_user).one()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user
    try:
        with TestClient(app) as client:
            yield client, db_mod.SessionLocal
    finally:
        app.dependency_overrides.clear()
        test_engine.dispose()
        db_mod.engine = previous_engine
        db_mod.SessionLocal = previous_session_local
        main_mod.engine = previous_main_engine
        settings.STORAGE_PATH = previous_storage
        settings.ENV = previous_env
        settings.API_RATE_LIMIT = previous_rate_limit
        settings.PARTY_SIGN_IN_WINDOW_MINUTES = previous_window


def _headers(user: str) -> dict[str, str]:
    return {"X-Test-User": user}


def _payload(**overrides) -> dict:
    now = local_now()
    payload = {
        "title": "报名测试活动",
        "category": "主题党日",
        "content": "测试报名签到流程。",
        "location": "A101",
        "start_at": (now + timedelta(days=3)).isoformat(),
        "end_at": (now + timedelta(days=3, hours=2)).isoformat(),
        "registration_deadline": (now + timedelta(days=2)).isoformat(),
        "target_roles": "全体学生",
        "target_member_ids": [],
        "max_participants": 10,
        "materials": [],
    }
    payload.update(overrides)
    return payload


def _published(client: TestClient, **overrides) -> int:
    created = client.post(
        "/api/v1/party/activities",
        json=_payload(**overrides),
        headers=_headers("admin"),
    )
    assert created.status_code == 200, created.text
    activity_id = created.json()["id"]
    published = client.post(
        f"/api/v1/party/activities/{activity_id}/publish",
        headers=_headers("admin"),
    )
    assert published.status_code == 200, published.text
    return activity_id


def _error_code(response) -> str:
    return response.json()["error"]["code"]


def test_registration_eligibility_and_database_uniqueness(registration_client) -> None:
    client, session_factory = registration_client
    all_students_id = _published(client)
    assert client.post(
        f"/api/v1/party/activities/{all_students_id}/register",
        headers=_headers("plain"),
    ).status_code == 200

    for user in ("teacher", "alumni"):
        denied = client.post(
            f"/api/v1/party/activities/{all_students_id}/register",
            headers=_headers(user),
        )
        assert denied.status_code == 403
        assert _error_code(denied) == "PARTY_REGISTRATION_FORBIDDEN"

    duplicate = client.post(
        f"/api/v1/party/activities/{all_students_id}/register",
        headers=_headers("plain"),
    )
    assert duplicate.status_code == 409
    assert _error_code(duplicate) == "PARTY_REGISTRATION_DUPLICATE"

    party_member_id = _published(client, target_roles="全体党员")
    assert client.post(
        f"/api/v1/party/activities/{party_member_id}/register",
        headers=_headers("formal"),
    ).status_code == 200
    activist_denied = client.post(
        f"/api/v1/party/activities/{party_member_id}/register",
        headers=_headers("activist"),
    )
    assert activist_denied.status_code == 403
    assert _error_code(activist_denied) == "PARTY_REGISTRATION_NOT_ELIGIBLE"

    with session_factory() as db:
        plain = db.query(User).filter(User.student_no == "plain").one()
        db.add(
            PartyActivityParticipant(activity_id=all_students_id, user_id=plain.id)
        )
        with pytest.raises(IntegrityError):
            db.commit()


def test_deadline_quota_cancel_and_reregister_release_capacity(
    registration_client,
) -> None:
    client, session_factory = registration_client
    activity_id = _published(client, max_participants=1)
    first = client.post(
        f"/api/v1/party/activities/{activity_id}/register",
        headers=_headers("plain"),
    )
    assert first.status_code == 200

    full = client.post(
        f"/api/v1/party/activities/{activity_id}/register",
        headers=_headers("plain2"),
    )
    assert full.status_code == 409
    assert _error_code(full) == "PARTY_REGISTRATION_FULL"

    cancelled = client.delete(
        f"/api/v1/party/activities/{activity_id}/register",
        headers=_headers("plain"),
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["registration_status"] == "cancelled"
    assert client.post(
        f"/api/v1/party/activities/{activity_id}/register",
        headers=_headers("plain2"),
    ).status_code == 200

    assert client.delete(
        f"/api/v1/party/activities/{activity_id}/register",
        headers=_headers("plain2"),
    ).status_code == 200
    reregistered = client.post(
        f"/api/v1/party/activities/{activity_id}/register",
        headers=_headers("plain"),
    )
    assert reregistered.status_code == 200
    assert reregistered.json()["registration_status"] == "registered"

    with session_factory() as db:
        activity = db.get(PartyActivity, activity_id)
        assert activity is not None
        after_deadline = activity.registration_deadline + timedelta(minutes=1)
    with patch(
        "backend.app.services.party_registration_service.local_now",
        return_value=after_deadline,
    ):
        late_cancel = client.delete(
            f"/api/v1/party/activities/{activity_id}/register",
            headers=_headers("plain"),
        )
    assert late_cancel.status_code == 409
    assert _error_code(late_cancel) == "PARTY_REGISTRATION_DEADLINE_PASSED"


def test_self_sign_in_window_and_activity_participation_contract(
    registration_client,
) -> None:
    client, session_factory = registration_client
    activity_id = _published(client)
    assert client.post(
        f"/api/v1/party/activities/{activity_id}/register",
        headers=_headers("plain"),
    ).status_code == 200

    too_early = client.post(
        f"/api/v1/party/activities/{activity_id}/sign-in",
        headers=_headers("plain"),
    )
    assert too_early.status_code == 409
    assert _error_code(too_early) == "PARTY_SIGN_IN_WINDOW_CLOSED"

    with session_factory() as db:
        activity = db.get(PartyActivity, activity_id)
        assert activity is not None
        within_window = activity.start_at - timedelta(minutes=30)
    with patch(
        "backend.app.services.party_registration_service.local_now",
        return_value=within_window,
    ):
        signed_in = client.post(
            f"/api/v1/party/activities/{activity_id}/sign-in",
            headers=_headers("plain"),
        )
    assert signed_in.status_code == 200
    assert signed_in.json()["attendance_status"] == "signed_in"
    assert signed_in.json()["sign_in_method"] == "self"
    assert signed_in.json()["sign_in_time"]

    detail = client.get(
        f"/api/v1/party/activities/{activity_id}", headers=_headers("plain")
    )
    assert detail.status_code == 200
    assert detail.json()["participant"] == detail.json()["my_participation"]
    assert detail.json()["my_participation"]["attendance_status"] == "signed_in"


def test_admin_manual_attendance_outside_window_and_student_forbidden(
    registration_client,
) -> None:
    client, session_factory = registration_client
    activity_id = _published(client)
    assert client.post(
        f"/api/v1/party/activities/{activity_id}/register",
        headers=_headers("plain"),
    ).status_code == 200
    with session_factory() as db:
        plain_id = db.query(User.id).filter(User.student_no == "plain").scalar()

    path = f"/api/v1/party/activities/{activity_id}/participants/{plain_id}/attendance"
    forbidden = client.put(
        path,
        json={"attendance_status": "signed_in"},
        headers=_headers("plain"),
    )
    assert forbidden.status_code == 403

    manual = client.put(
        path,
        json={"attendance_status": "signed_in"},
        headers=_headers("admin"),
    )
    assert manual.status_code == 200
    assert manual.json()["sign_in_method"] == "manual"
    assert manual.json()["sign_in_time"]

    absent = client.put(
        path,
        json={"attendance_status": "absent"},
        headers=_headers("admin"),
    )
    assert absent.status_code == 200
    assert absent.json()["attendance_status"] == "absent"
    assert absent.json()["sign_in_time"] is None
    assert absent.json()["sign_in_method"] is None


def test_mine_returns_only_authenticated_users_profile_and_records(
    registration_client,
) -> None:
    client, _ = registration_client
    activity_id = _published(client)
    assert client.post(
        f"/api/v1/party/activities/{activity_id}/register",
        headers=_headers("formal"),
    ).status_code == 200
    assert client.post(
        f"/api/v1/party/activities/{activity_id}/register",
        headers=_headers("plain"),
    ).status_code == 200

    formal = client.get("/api/v1/party/mine", headers=_headers("formal"))
    assert formal.status_code == 200
    body = formal.json()
    assert body["party"]["party_type"] == "正式党员"
    assert body["records"] == body["participation_records"]
    assert len(body["records"]) == 1
    assert body["records"][0]["user_id"] != client.get(
        "/api/v1/party/mine", headers=_headers("plain")
    ).json()["records"][0]["user_id"]
    assert body["records"][0]["activity"]["id"] == activity_id

    plain = client.get("/api/v1/party/mine", headers=_headers("plain"))
    assert plain.status_code == 200
    assert plain.json()["party"] == {}

    for user in ("teacher", "alumni"):
        denied = client.get("/api/v1/party/mine", headers=_headers(user))
        assert denied.status_code == 403
