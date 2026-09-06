from __future__ import annotations

from datetime import datetime, timedelta
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
from backend.app.core.storage import StorageService
from backend.app.models.notification import Notification
from backend.app.models.party import PartyActivity
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
def activity_client(tmp_path: Path):
    from backend.app import main as main_mod
    from backend.app.core import database as db_mod

    previous_engine = db_mod.engine
    previous_session_local = db_mod.SessionLocal
    previous_main_engine = main_mod.engine
    previous_storage = settings.STORAGE_PATH
    previous_limit = settings.PARTY_MATERIAL_MAX_MB
    previous_env = settings.ENV
    previous_rate_limit = settings.API_RATE_LIMIT

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
    settings.PARTY_MATERIAL_MAX_MB = 1
    settings.ENV = "test"
    settings.API_RATE_LIMIT = 100000

    Base.metadata.create_all(bind=test_engine)
    db = db_mod.SessionLocal()
    users = [
        User(student_no="formal", name="正式党员", password_hash="unused", role="student", status="active"),
        User(student_no="probation", name="预备党员", password_hash="unused", role="student", status="active"),
        User(student_no="activist", name="积极分子", password_hash="unused", role="student", status="active"),
        User(student_no="plain", name="普通学生", password_hash="unused", role="student", status="active"),
        User(student_no="teacher", name="教师", password_hash="unused", role="teacher", status="active"),
        User(student_no="alumni", name="校友", password_hash="unused", role="alumni", status="active"),
        User(student_no="admin", name="管理员", password_hash="unused", role="admin", status="active"),
    ]
    users[0].party = _party("正式党员")
    users[1].party = _party("预备党员")
    users[2].party = _party("入党积极分子")
    db.add_all(users)
    db.commit()
    db.close()

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
        settings.PARTY_MATERIAL_MAX_MB = previous_limit
        settings.ENV = previous_env
        settings.API_RATE_LIMIT = previous_rate_limit


def _headers(user: str = "admin") -> dict[str, str]:
    return {"X-Test-User": user}


def _payload(**overrides) -> dict:
    now = local_now()
    value = {
        "title": "八月主题党日",
        "category": "主题党日",
        "content": "集中开展理论学习与交流。",
        "location": "教学楼 A101",
        "start_at": (now + timedelta(days=5)).isoformat(),
        "end_at": (now + timedelta(days=5, hours=2)).isoformat(),
        "registration_deadline": (now + timedelta(days=2)).isoformat(),
        "target_roles": "全体党员",
        "target_member_ids": [],
        "max_participants": 30,
        "materials": [{"file_id": "seed.pdf", "original_name": "学习材料.pdf"}],
    }
    value.update(overrides)
    return value


def _create(client: TestClient, **overrides):
    return client.post(
        "/api/v1/party/activities",
        json=_payload(**overrides),
        headers=_headers(),
    )


def test_activity_crud_permissions_enums_and_filters(activity_client) -> None:
    client, _ = activity_client
    forbidden = client.post(
        "/api/v1/party/activities", json=_payload(), headers=_headers("plain")
    )
    assert forbidden.status_code == 403
    invalid = _create(client, category="会议")
    assert invalid.status_code == 422
    invalid_target = _create(client, target_roles="所有人")
    assert invalid_target.status_code == 422
    missing_targets = _create(client, target_roles="指定人员", target_member_ids=[])
    assert missing_targets.status_code == 422

    frontend_payload = _payload()
    frontend_payload["target_member_ids_json"] = frontend_payload.pop("target_member_ids")
    frontend_payload["materials_json"] = frontend_payload.pop("materials")
    created = client.post(
        "/api/v1/party/activities", json=frontend_payload, headers=_headers()
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["status"] == "draft"
    assert body["materials"][0]["file_id"] == "seed.pdf"
    assert body["materials_json"] == body["materials"]
    assert body["target_member_ids_json"] == body["target_member_ids"]

    activity_id = body["id"]
    updated = client.put(
        f"/api/v1/party/activities/{activity_id}",
        json={"title": "修改后的主题党日", "location": "教学楼 A102"},
        headers=_headers(),
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "修改后的主题党日"
    assert client.put(
        f"/api/v1/party/activities/{activity_id}",
        json={"title": "越权修改"},
        headers=_headers("formal"),
    ).status_code == 403

    year = local_now().year
    listed = client.get(
        f"/api/v1/party/activities?status=draft&category=主题党日&year={year}",
        headers=_headers(),
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == activity_id
    assert client.get(
        f"/api/v1/party/activities/{activity_id}", headers=_headers()
    ).status_code == 200


def test_publish_deadline_exact_transitions_locks_and_notification(activity_client) -> None:
    client, session_factory = activity_client
    invalid = _create(
        client,
        registration_deadline=(local_now() + timedelta(days=6)).isoformat(),
    ).json()
    rejected = client.post(
        f"/api/v1/party/activities/{invalid['id']}/publish", headers=_headers()
    )
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "PARTY_ACTIVITY_DEADLINE_INVALID"

    activity_id = _create(client).json()["id"]
    skipped = client.put(
        f"/api/v1/party/activities/{activity_id}/status",
        json={"status": "ongoing"},
        headers=_headers(),
    )
    assert skipped.status_code == 409
    published = client.post(
        f"/api/v1/party/activities/{activity_id}/publish", headers=_headers()
    )
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "published"

    locked_values = [
        {"registration_deadline": None},
        {"target_roles": "全体学生"},
        {"target_member_ids": [1]},
        {"max_participants": 50},
    ]
    for values in locked_values:
        response = client.put(
            f"/api/v1/party/activities/{activity_id}",
            json=values,
            headers=_headers(),
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "PARTY_ACTIVITY_REGISTRATION_LOCKED"

    still_editable = client.put(
        f"/api/v1/party/activities/{activity_id}",
        json={"content": "发布后补充说明"},
        headers=_headers(),
    )
    assert still_editable.status_code == 200
    with session_factory() as db:
        notices = (
            db.query(Notification)
            .filter(
                Notification.type == "party_activity_notice",
                Notification.ref_type == "party_activity",
                Notification.ref_id == activity_id,
            )
            .all()
        )
        assert {notice.user_id for notice in notices} == {
            db.query(User.id).filter(User.student_no == "formal").scalar(),
            db.query(User.id).filter(User.student_no == "probation").scalar(),
        }

    for target in ("ongoing", "finished", "archived"):
        changed = client.put(
            f"/api/v1/party/activities/{activity_id}/status",
            json={"status": target},
            headers=_headers(),
        )
        assert changed.status_code == 200
        assert changed.json()["status"] == target
    assert client.put(
        f"/api/v1/party/activities/{activity_id}/status",
        json={"status": "finished"},
        headers=_headers(),
    ).status_code == 409


def test_activity_visibility_by_target_role_and_draft(activity_client) -> None:
    client, session_factory = activity_client
    with session_factory() as db:
        admin_id = db.query(User.id).filter(User.student_no == "admin").scalar()
        plain_id = db.query(User.id).filter(User.student_no == "plain").scalar()
        teacher_id = db.query(User.id).filter(User.student_no == "teacher").scalar()
        targets = [
            ("党员", "全体党员", []),
            ("含积极分子", "党员与积极分子", []),
            ("预备与积极", "预备党员与积极分子", []),
            ("公开", "全体学生", []),
            ("指定", "指定人员", [plain_id, teacher_id]),
        ]
        for title, target_roles, target_ids in targets:
            payload = _payload(title=title, target_roles=target_roles, target_member_ids=target_ids)
            payload.pop("materials")
            for field in ("start_at", "end_at", "registration_deadline"):
                payload[field] = datetime.fromisoformat(payload[field])
            activity = PartyActivity(
                **{key: value for key, value in payload.items() if key != "target_member_ids"},
                created_by=admin_id,
                status="published",
            )
            activity.target_member_ids = target_ids
            db.add(activity)
        draft_payload = _payload(title="草稿")
        for field in ("start_at", "end_at", "registration_deadline"):
            draft_payload[field] = datetime.fromisoformat(draft_payload[field])
        draft = PartyActivity(
            **{
                key: value
                for key, value in draft_payload.items()
                if key not in {"target_member_ids", "materials"}
            },
            created_by=admin_id,
            status="draft",
        )
        db.add(draft)
        db.commit()

    expected = {
        "formal": {"党员", "含积极分子", "公开"},
        "probation": {"党员", "含积极分子", "预备与积极", "公开"},
        "activist": {"含积极分子", "预备与积极", "公开"},
        "plain": {"公开", "指定"},
        "teacher": {"指定"},
        "alumni": set(),
    }
    for user, titles in expected.items():
        response = client.get("/api/v1/party/activities", headers=_headers(user))
        assert response.status_code == 200
        assert {item["title"] for item in response.json()["items"]} == titles
    admin = client.get("/api/v1/party/activities", headers=_headers())
    assert {item["title"] for item in admin.json()["items"]} == {
        "党员",
        "含积极分子",
        "预备与积极",
        "公开",
        "指定",
        "草稿",
    }


def test_activity_material_upload_summary_and_archived_soft_delete(activity_client) -> None:
    client, session_factory = activity_client
    activity_id = _create(client).json()["id"]
    path = f"/api/v1/party/activities/{activity_id}/materials"
    assert client.post(
        path,
        files={"file": ("材料.txt", b"text", "text/plain")},
        headers=_headers(),
    ).status_code == 400
    assert client.post(
        path,
        files={"file": ("large.png", b"x" * (1024 * 1024 + 1), "image/png")},
        headers=_headers(),
    ).status_code == 400
    uploaded = client.post(
        path,
        files={"file": ("学习材料.pdf", b"%PDF-1.7 content", "application/pdf")},
        headers=_headers(),
    )
    assert uploaded.status_code == 200, uploaded.text
    attachment = uploaded.json()["materials"][-1]
    assert attachment["original_name"] == "学习材料.pdf"
    assert attachment["file_id"] == attachment["stored_name"]
    assert StorageService.file_exists("party_activities", activity_id, attachment["stored_name"])

    assert client.delete(
        f"/api/v1/party/activities/{activity_id}", headers=_headers()
    ).status_code == 409
    assert client.post(
        f"/api/v1/party/activities/{activity_id}/summary",
        json={"summary": "总结"},
        headers=_headers(),
    ).status_code == 409
    assert client.post(
        f"/api/v1/party/activities/{activity_id}/publish", headers=_headers()
    ).status_code == 200
    assert client.put(
        f"/api/v1/party/activities/{activity_id}/status",
        json={"status": "ongoing"},
        headers=_headers(),
    ).status_code == 200
    summary = client.post(
        f"/api/v1/party/activities/{activity_id}/summary",
        json={
            "summary": "活动顺利完成",
            "summary_attachments_json": [{"file_id": "photo.png", "original_name": "合影.png"}],
        },
        headers=_headers(),
    )
    assert summary.status_code == 200
    assert summary.json()["summary_attachments"][0]["file_id"] == "photo.png"
    assert client.put(
        f"/api/v1/party/activities/{activity_id}/status",
        json={"status": "finished"},
        headers=_headers(),
    ).status_code == 200
    archived = client.post(
        f"/api/v1/party/activities/{activity_id}/summary",
        json={"summary": "活动顺利完成", "archive": True},
        headers=_headers(),
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    assert client.put(
        f"/api/v1/party/activities/{activity_id}",
        json={"summary": "归档后修改"},
        headers=_headers(),
    ).status_code == 409
    deleted = client.delete(
        f"/api/v1/party/activities/{activity_id}", headers=_headers()
    )
    assert deleted.status_code == 200
    assert client.get(
        f"/api/v1/party/activities/{activity_id}", headers=_headers()
    ).status_code == 404
    with session_factory() as db:
        row = db.get(PartyActivity, activity_id)
        assert row is not None and row.deleted_at is not None


def test_activity_static_routes_are_registered_before_dynamic_detail() -> None:
    from backend.app.api.routes.party import router

    paths = [route.path for route in router.routes]
    assert paths.index("/activities") < paths.index("/activities/{activity_id}")
    assert "/activities/{activity_id}/publish" in paths
    assert "/activities/{activity_id}/status" in paths
    assert "/activities/{activity_id}/materials" in paths
