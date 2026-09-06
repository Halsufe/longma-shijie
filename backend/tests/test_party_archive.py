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
from backend.app.models.party import PartyActivity, PartyActivityParticipant, PartyMaterial
from backend.app.models.user import User


def _party(party_type: str, *, class_name: str = "数据25级", **extra) -> dict:
    value = {
        "party_type": party_type,
        "branch_name": "大数据党支部",
        "class_name": class_name,
        "grade": "25" if class_name == "数据25级" else "24",
        "apply_date": "2024-01",
        "apply_status": "递交申请",
    }
    value.update(extra)
    return value


@pytest.fixture()
def archive_client(tmp_path):
    from backend.app import main as main_mod
    from backend.app.core import database as db_mod

    old_engine, old_session, old_main = db_mod.engine, db_mod.SessionLocal, main_mod.engine
    old_storage, old_env, old_limit = settings.STORAGE_PATH, settings.ENV, settings.API_RATE_LIMIT
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    db_mod.engine = engine
    db_mod.SessionLocal = sessionmaker(bind=engine, future=True)
    main_mod.engine = engine
    settings.STORAGE_PATH = str(tmp_path / "storage")
    settings.ENV = "test"
    settings.API_RATE_LIMIT = 100000
    Base.metadata.create_all(engine)
    with db_mod.SessionLocal() as db:
        users = [
            User(student_no="formal", name="正式党员", password_hash="x", role="student", status="active"),
            User(student_no="probation", name="预备党员", password_hash="x", role="student", status="active"),
            User(student_no="activist", name="积极分子", password_hash="x", role="student", status="active"),
            User(student_no="plain", name="普通学生", password_hash="x", role="student", status="active"),
            User(student_no="admin", name="管理员", password_hash="x", role="admin", status="active"),
        ]
        users[0].party = _party(
            "正式党员",
            apply_status="转为正式党员",
            activist_date="2024-02",
            target_date="2024-03",
            probation_date="2024-04",
            full_date="2026-05",
        )
        users[1].party = _party("预备党员", apply_status="接受为预备党员")
        users[2].party = _party("入党积极分子", class_name="数据24级", apply_status="确定为积极分子")
        db.add_all(users)
        db.commit()
        now = local_now()
        finished = PartyActivity(
            title="归档主题党日",
            category="主题党日",
            content="学习",
            location="A101",
            start_at=now - timedelta(days=5),
            end_at=now - timedelta(days=5, hours=-2),
            registration_deadline=now - timedelta(days=6),
            target_roles="全体党员",
            status="finished",
            created_by=users[4].id,
            summary="已完成",
        )
        finished.materials = [{"name": "党章.pdf", "uploaded_at": now.isoformat()}]
        draft = PartyActivity(
            title="草稿活动",
            category="理论学习",
            content="草稿",
            location="A102",
            start_at=now + timedelta(days=2),
            end_at=now + timedelta(days=2, hours=1),
            target_roles="全体学生",
            status="draft",
            created_by=users[4].id,
        )
        db.add_all([finished, draft])
        db.flush()
        db.add_all(
            [
                PartyActivityParticipant(
                    activity_id=finished.id,
                    user_id=users[0].id,
                    registration_status="registered",
                    attendance_status="signed_in",
                    sign_in_method="self",
                    sign_in_time=finished.start_at,
                ),
                PartyActivityParticipant(
                    activity_id=finished.id,
                    user_id=users[1].id,
                    registration_status="registered",
                    attendance_status="absent",
                ),
                PartyMaterial(
                    user_id=users[0].id,
                    material_type="思想汇报",
                    title="思想汇报",
                    original_name="report.pdf",
                    stored_name="stored.pdf",
                    mime_type="application/pdf",
                    size=10,
                    uploaded_by=users[4].id,
                ),
            ]
        )
        db.commit()
        ids = {"finished": finished.id, "draft": draft.id, "formal": users[0].id}

    app = main_mod.create_app()

    def override_db():
        with db_mod.SessionLocal() as db:
            yield db

    def override_user(x_test_user: str = Header("admin"), db: Session = Depends(get_db)):
        return db.query(User).filter(User.student_no == x_test_user).one()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    try:
        with TestClient(app) as client:
            yield client, db_mod.SessionLocal, ids
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
        db_mod.engine, db_mod.SessionLocal, main_mod.engine = old_engine, old_session, old_main
        settings.STORAGE_PATH, settings.ENV, settings.API_RATE_LIMIT = old_storage, old_env, old_limit


def _h(user: str = "admin") -> dict[str, str]:
    return {"X-Test-User": user}


def test_activity_archive_is_admin_only_complete_and_read_only(archive_client) -> None:
    client, _, ids = archive_client
    assert client.get(
        f"/api/v1/party/activities/{ids['finished']}/archive", headers=_h("plain")
    ).status_code == 403
    not_ready = client.get(
        f"/api/v1/party/activities/{ids['draft']}/archive", headers=_h()
    )
    assert not_ready.status_code == 409
    archive = client.get(
        f"/api/v1/party/activities/{ids['finished']}/archive", headers=_h()
    )
    assert archive.status_code == 200, archive.text
    body = archive.json()
    assert body["activity"]["summary"] == "已完成"
    assert body["activity"]["materials"][0]["name"] == "党章.pdf"
    assert {member["name"] for member in body["expected_members"]} == {"正式党员", "预备党员"}
    assert body["expected_count"] == 2
    assert body["registered_count"] == 2
    assert body["signed_in_count"] == 1
    assert body["absent_count"] == 1


def test_member_archive_timeline_materials_and_combined_filters(archive_client) -> None:
    client, _, ids = archive_client
    archive = client.get(
        f"/api/v1/party/members/{ids['formal']}/archive", headers=_h()
    )
    assert archive.status_code == 200
    assert [item["key"] for item in archive.json()["timeline"]] == [
        "apply_date",
        "activist_date",
        "target_date",
        "probation_date",
        "full_date",
    ]
    assert archive.json()["materials"][0]["title"] == "思想汇报"
    filtered = client.get(
        f"/api/v1/party/archives?year={local_now().year}&category=主题党日&class_name=数据25级&party_type=正式党员&apply_status=转为正式党员",
        headers=_h(),
    )
    assert filtered.status_code == 200
    assert filtered.json()["activity_total"] == 1
    assert filtered.json()["member_total"] == 1


def test_csv_exports_have_bom_filters_and_row_limit(archive_client) -> None:
    client, _, ids = archive_client
    members = client.post(
        "/api/v1/party/stats/export",
        json={"export_type": "members", "party_type": "正式党员"},
        headers=_h(),
    )
    assert members.status_code == 200
    assert members.content.startswith(b"\xef\xbb\xbf")
    text = members.content.decode("utf-8-sig")
    assert "正式党员" in text and "预备党员" not in text
    participants = client.post(
        "/api/v1/party/stats/export",
        json={"export_type": "participants", "activity_id": ids["finished"]},
        headers=_h(),
    )
    assert participants.status_code == 200
    assert "归档主题党日" in participants.content.decode("utf-8-sig")
    limited = client.post(
        "/api/v1/party/stats/export",
        json={"export_type": "members", "max_rows": 1},
        headers=_h(),
    )
    assert limited.status_code == 422
    assert limited.json()["error"]["code"] == "PARTY_EXPORT_LIMIT_EXCEEDED"


def test_archive_static_routes_exist() -> None:
    from backend.app.api.routes.party import router

    paths = {route.path for route in router.routes}
    assert "/archives" in paths
    assert "/members/{user_id}/archive" in paths
    assert "/activities/{activity_id}/archive" in paths
    assert "/stats/export" in paths


def test_stats_routes_require_admin_and_validate_type(archive_client) -> None:
    client, _, _ = archive_client
    assert client.get("/api/v1/party/stats", headers=_h("plain")).status_code == 403
    invalid = client.get("/api/v1/party/stats?type=unknown", headers=_h())
    assert invalid.status_code == 422
    valid = client.get("/api/v1/party/stats?type=member_counts", headers=_h())
    assert valid.status_code == 200
    assert valid.json()["member_counts"]["total"] == 3
