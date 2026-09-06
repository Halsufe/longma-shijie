from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi import Depends, Header
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.deps import get_current_user
from backend.app.core.config import settings
from backend.app.core.database import Base, get_db, local_now
from backend.app.models.achievement import Achievement
from backend.app.models.party import PartyActivity, PartyActivityParticipant
from backend.app.models.user import User
from backend.app.services.achievement_service import (
    AchievementValidationError,
    validate_details,
)


def _party(party_type: str, **overrides) -> dict:
    value = {
        "party_type": party_type,
        "branch_name": "许国志大数据英才班党支部",
        "class_name": "大数据25级",
        "grade": "25",
        "apply_date": "2024-01",
        "apply_status": "递交申请",
    }
    value.update(overrides)
    return value


@pytest.fixture()
def link_client(tmp_path):
    from backend.app import main as main_mod
    from backend.app.core import database as db_mod

    previous_engine = db_mod.engine
    previous_session_local = db_mod.SessionLocal
    previous_main_engine = main_mod.engine
    previous_storage = settings.STORAGE_PATH
    previous_env = settings.ENV
    previous_rate_limit = settings.API_RATE_LIMIT

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    db_mod.engine = engine
    db_mod.SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        future=True,
    )
    main_mod.engine = engine
    settings.STORAGE_PATH = str(tmp_path / "storage")
    settings.ENV = "test"
    settings.API_RATE_LIMIT = 100000

    Base.metadata.create_all(bind=engine)
    with db_mod.SessionLocal() as db:
        formal = User(
            student_no="formal",
            name="正式党员",
            password_hash="unused",
            role="student",
            status="active",
        )
        formal.party = _party(
            "正式党员",
            apply_status="转为正式党员",
            full_date="2025-05",
            party_join_date="2025-05",
        )
        probation = User(
            student_no="probation",
            name="预备党员",
            password_hash="unused",
            role="student",
            status="active",
        )
        probation.party = _party(
            "预备党员",
            apply_status="接受为预备党员",
            probation_date="2025-06",
        )
        activist = User(
            student_no="activist",
            name="积极分子",
            password_hash="unused",
            role="student",
            status="active",
        )
        activist.party = _party("入党积极分子")
        plain = User(
            student_no="plain",
            name="普通学生",
            password_hash="unused",
            role="student",
            status="active",
        )
        broken = User(
            student_no="broken",
            name="旧档案党员",
            password_hash="unused",
            role="student",
            status="active",
        )
        broken.party = _party("正式党员", apply_status="转为正式党员")
        admin = User(
            student_no="admin",
            name="管理员",
            password_hash="unused",
            role="admin",
            status="active",
        )
        db.add_all([formal, probation, activist, plain, broken, admin])
        db.commit()

    app = main_mod.create_app()

    def override_get_db():
        session = db_mod.SessionLocal()
        try:
            yield session
        finally:
            session.close()

    def override_current_user(
        x_test_user: str = Header("formal"),
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
        engine.dispose()
        db_mod.engine = previous_engine
        db_mod.SessionLocal = previous_session_local
        main_mod.engine = previous_main_engine
        settings.STORAGE_PATH = previous_storage
        settings.ENV = previous_env
        settings.API_RATE_LIMIT = previous_rate_limit


def _headers(user: str) -> dict[str, str]:
    return {"X-Test-User": user}


def _user(db: Session, student_no: str) -> User:
    return db.query(User).filter(User.student_no == student_no).one()


def _activity(
    db: Session,
    *,
    user: User,
    category: str,
    attendance_status: str = "signed_in",
) -> PartyActivity:
    now = local_now()
    admin = _user(db, "admin")
    activity = PartyActivity(
        title=f"{category}联动测试",
        category=category,
        content="党建活动过程记录",
        location="社区服务中心",
        start_at=now - timedelta(days=2),
        end_at=now - timedelta(days=2) + timedelta(hours=2),
        registration_deadline=now - timedelta(days=3),
        target_roles="全体学生",
        status="finished",
        created_by=admin.id,
        summary="活动已顺利完成",
    )
    db.add(activity)
    db.flush()
    db.add(
        PartyActivityParticipant(
            activity_id=activity.id,
            user_id=user.id,
            registration_status="registered",
            attendance_status=attendance_status,
            sign_in_time=now if attendance_status == "signed_in" else None,
            sign_in_method="manual" if attendance_status == "signed_in" else None,
        )
    )
    db.commit()
    db.refresh(activity)
    return activity


def test_identity_link_creates_valid_pending_organization_and_prevents_duplicate(
    link_client,
) -> None:
    client, session_factory = link_client
    linked = client.post(
        "/api/v1/party/achievements/link",
        json={"link_type": "identity"},
        headers=_headers("formal"),
    )
    assert linked.status_code == 200, linked.text
    body = linked.json()
    assert body["category"] == "organization"
    assert body["status"] == "pending"
    assert body["is_public"] is False
    assert body["title"] == "许国志大数据英才班党支部党员"
    assert body["achievement_date"] == "2025-05"
    assert body["details"]["position"] == "正式党员"
    assert body["details"]["assessment"] == "合格"
    assert body["details"]["honor_title"] == "无"
    assert body["details"]["end_year"] == "进行中"
    assert body["details"]["source_type"] == "party"
    assert body["details"]["source_id"].startswith("identity:")
    assert validate_details("organization", body["details"]) == body["details"]

    duplicate = client.post(
        "/api/v1/party/achievements/link",
        json={"type": "party_identity"},
        headers=_headers("formal"),
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "PARTY_ACHIEVEMENT_DUPLICATE"
    with session_factory() as db:
        assert db.query(Achievement).count() == 1


def test_admin_can_link_probation_identity_but_activist_and_cross_user_are_denied(
    link_client,
) -> None:
    client, session_factory = link_client
    with session_factory() as db:
        probation_id = _user(db, "probation").id
    linked = client.post(
        "/api/v1/party/achievements/link",
        json={"source_type": "member", "user_id": probation_id},
        headers=_headers("admin"),
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()["details"]["position"] == "预备党员"

    activist = client.post(
        "/api/v1/party/achievements/link",
        json={},
        headers=_headers("activist"),
    )
    assert activist.status_code == 403
    assert activist.json()["error"]["code"] == "PARTY_ACHIEVEMENT_IDENTITY_NOT_ELIGIBLE"

    cross_user = client.post(
        "/api/v1/party/achievements/link",
        json={"user_id": probation_id},
        headers=_headers("formal"),
    )
    assert cross_user.status_code == 403


@pytest.mark.parametrize(
    ("category", "expected_category"),
    [("志愿公益", "social"), ("主题党日", "organization")],
)
def test_signed_activity_maps_by_nature_and_satisfies_template(
    link_client, category: str, expected_category: str
) -> None:
    client, session_factory = link_client
    with session_factory() as db:
        plain = _user(db, "plain")
        user_id = plain.id
        activity_id = _activity(db, user=plain, category=category).id

    linked = client.post(
        "/api/v1/party/achievements/link",
        json={"activity_id": activity_id},
        headers=_headers("plain"),
    )
    assert linked.status_code == 200, linked.text
    body = linked.json()
    assert body["user_id"] == user_id
    assert body["category"] == expected_category
    assert body["status"] == "pending"
    assert body["details"]["source_type"] == "party"
    assert body["details"]["source_id"] == f"activity:{activity_id}"
    assert validate_details(expected_category, body["details"]) == body["details"]
    if expected_category == "social":
        assert body["details"]["practice_unit"] == "社区服务中心"
        assert body["details"]["member_names"] == "普通学生"
        assert body["details"]["is_team"] is True
    else:
        assert body["details"]["honor_title"] == "无"


def test_unsigned_activity_is_rejected_without_partial_achievement(link_client) -> None:
    client, session_factory = link_client
    with session_factory() as db:
        plain = _user(db, "plain")
        activity_id = _activity(
            db,
            user=plain,
            category="志愿公益",
            attendance_status="none",
        ).id

    denied = client.post(
        "/api/v1/party/achievements/link",
        json={"link_type": "activity", "activity_id": activity_id},
        headers=_headers("plain"),
    )
    assert denied.status_code == 409
    assert denied.json()["error"]["code"] == "PARTY_ACHIEVEMENT_ATTENDANCE_REQUIRED"
    with session_factory() as db:
        assert db.query(Achievement).count() == 0


def test_template_mapping_error_is_readable_and_atomic(link_client) -> None:
    client, session_factory = link_client
    failed = client.post(
        "/api/v1/party/achievements/link",
        json={},
        headers=_headers("broken"),
    )
    assert failed.status_code == 422
    assert failed.json()["error"]["code"] == "PARTY_ACHIEVEMENT_MAPPING_INVALID"
    assert "YYYY-MM" in failed.json()["error"]["message"]
    with session_factory() as db:
        assert db.query(Achievement).count() == 0


def test_only_controlled_source_metadata_bypasses_template_field_rejection() -> None:
    details = {
        "position": "正式党员",
        "assessment": "合格",
        "honor_title": "无",
        "start_year": 2025,
        "start_month": 5,
        "end_year": "进行中",
        "end_month": "进行中",
        "source_type": "party",
        "source_id": "identity:1",
    }
    assert validate_details("organization", details) == details
    details["unexpected"] = "仍应拒绝"
    with pytest.raises(AchievementValidationError):
        validate_details("organization", details)
