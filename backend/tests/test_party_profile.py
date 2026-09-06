from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import Depends, Header
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.api.deps import get_current_user, require_party_member
from backend.app.core.config import settings
from backend.app.core.database import Base, get_db, local_now
from backend.app.core.errors import AppException
from backend.app.core.storage import StorageService
from backend.app.models.audit import AuditLog
from backend.app.models.party import PartyMaterial
from backend.app.models.user import User
from backend.app.schemas.user import UserInfo
from backend.app.services.party_profile_service import PartyProfileService


CLASS_NAME = "测试数据25级"


def _profile(**overrides) -> dict:
    value = {
        "party_type": "入党积极分子",
        "branch_name": "大数据党支部",
        "class_name": CLASS_NAME,
        "grade": "25",
        "apply_date": "2025-01",
        "apply_status": "递交申请",
    }
    value.update(overrides)
    return value


@pytest.fixture()
def party_client(tmp_path: Path):
    from backend.app.core import database as db_mod
    from backend.app import main as main_mod

    previous_engine = db_mod.engine
    previous_session_local = db_mod.SessionLocal
    previous_main_engine = main_mod.engine
    previous_storage = settings.STORAGE_PATH
    previous_classes = settings.PARTY_CLASSES
    previous_limit = settings.PARTY_MATERIAL_MAX_MB
    previous_env = settings.ENV
    previous_rate_limit = settings.API_RATE_LIMIT

    test_engine = create_engine(
        f"sqlite:///{tmp_path / 'party-profile.db'}",
        connect_args={"check_same_thread": False},
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
    settings.PARTY_CLASSES = f"{CLASS_NAME},测试数据24级"
    settings.PARTY_MATERIAL_MAX_MB = 1
    settings.ENV = "test"
    settings.API_RATE_LIMIT = 100000

    Base.metadata.create_all(bind=test_engine)
    db = db_mod.SessionLocal()
    db.add_all(
        [
            User(
                student_no="s1",
                name="学生一",
                password_hash="unused",
                role="student",
                status="active",
            ),
            User(
                student_no="s2",
                name="学生二",
                password_hash="unused",
                role="student",
                status="active",
            ),
            User(
                student_no="s3",
                name="学生三",
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
                student_no="alumni",
                name="校友",
                password_hash="unused",
                role="alumni",
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
    db.close()

    app = main_mod.create_app()

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
        settings.PARTY_CLASSES = previous_classes
        settings.PARTY_MATERIAL_MAX_MB = previous_limit
        settings.ENV = previous_env
        settings.API_RATE_LIMIT = previous_rate_limit


def _user_id(session_factory, student_no: str) -> int:
    with session_factory() as db:
        return db.query(User.id).filter(User.student_no == student_no).scalar()


def _create_member(
    client: TestClient,
    session_factory,
    student_no: str = "s1",
    **overrides,
):
    payload = {
        "user_id": _user_id(session_factory, student_no),
        **_profile(**overrides),
    }
    return client.post(
        "/api/v1/party/members",
        json=payload,
        headers={"X-Test-User": "admin"},
    )


def test_user_party_property_and_user_info_are_legacy_safe() -> None:
    user = User(
        id=7,
        student_no="legacy",
        name="旧用户",
        password_hash="unused",
        role="student",
        status="active",
    )
    user.party_json = "not-json"
    assert user.party == {}
    user.party_json = "[]"
    assert user.party == {}
    user.party = _profile()
    user.created_at = local_now()
    user.updated_at = local_now()
    assert json.loads(user.party_json) == _profile()
    assert UserInfo.model_validate(user).party == _profile()


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"party_type": "群众"}, "party_type"),
        ({"apply_status": "未知阶段"}, "apply_status"),
        ({"class_name": "未配置班级"}, "PARTY_CLASSES"),
        ({"apply_date": "2025-13"}, "YYYY-MM"),
        (
            {
                "apply_status": "确定为积极分子",
                "activist_date": "2024-12",
            },
            "单调递增",
        ),
        (
            {"apply_status": "停止发展", "stop_reason": None},
            "stop_reason",
        ),
        (
            {
                "party_type": "正式党员",
                "apply_status": "递交申请",
            },
            "正式党员",
        ),
        (
            {
                "party_type": "正式党员",
                "apply_status": "停止发展",
                "stop_reason": "组织决定",
                "activist_date": None,
                "target_date": None,
                "probation_date": None,
                "full_date": None,
            },
            "正式党员档案必须填写",
        ),
    ],
)
def test_profile_validation_rejects_invalid_values(
    overrides: dict, message: str, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "PARTY_CLASSES", CLASS_NAME)
    with pytest.raises(AppException) as exc_info:
        PartyProfileService.validate_profile(_profile(**overrides))
    assert exc_info.value.status_code == 422
    assert message in exc_info.value.message


def test_require_party_member_rejects_nonmember_teacher_and_alumni() -> None:
    member = User(role="student", party_json=json.dumps(_profile(), ensure_ascii=False))
    plain_student = User(role="student", party_json="{}")
    teacher = User(role="teacher", party_json=json.dumps(_profile(), ensure_ascii=False))
    alumni = User(role="alumni", party_json=json.dumps(_profile(), ensure_ascii=False))

    assert require_party_member(member) is member
    for user in (plain_student, teacher, alumni):
        with pytest.raises(AppException) as exc_info:
            require_party_member(user)
        assert exc_info.value.status_code == 403


def test_member_crud_filters_permissions_and_soft_delete(party_client) -> None:
    client, session_factory = party_client
    forbidden = client.get(
        "/api/v1/party/members", headers={"X-Test-User": "s1"}
    )
    assert forbidden.status_code == 403

    created = _create_member(client, session_factory)
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["party_type"] == "入党积极分子"
    assert body["party"]["class_name"] == CLASS_NAME

    duplicate = _create_member(client, session_factory)
    assert duplicate.status_code == 409

    listed = client.get(
        f"/api/v1/party/members?class_name={CLASS_NAME}&party_type=入党积极分子",
        headers={"X-Test-User": "admin"},
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["page_size"] == 20

    user_id = body["user_id"]
    updated = client.put(
        f"/api/v1/party/members/{user_id}",
        json={"remark": "重点培养"},
        headers={"X-Test-User": "admin"},
    )
    assert updated.status_code == 200
    assert updated.json()["remark"] == "重点培养"

    bypass = client.put(
        f"/api/v1/party/members/{user_id}",
        json={"apply_status": "确定为积极分子"},
        headers={"X-Test-User": "admin"},
    )
    assert bypass.status_code == 409

    deleted = client.delete(
        f"/api/v1/party/members/{user_id}",
        headers={"X-Test-User": "admin"},
    )
    assert deleted.status_code == 200
    assert client.get(
        "/api/v1/party/members", headers={"X-Test-User": "admin"}
    ).json()["total"] == 0
    with session_factory() as db:
        user = db.get(User, user_id)
        assert user is not None and user.deleted_at is None
        assert user.party["deleted_at"]

    restored = _create_member(client, session_factory)
    assert restored.status_code == 200


def test_member_can_be_created_by_student_no(party_client) -> None:
    client, session_factory = party_client
    response = client.post(
        "/api/v1/party/members",
        json={"student_no": "s1", **_profile()},
        headers={"X-Test-User": "admin"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["student_no"] == "s1"

    with session_factory() as db:
        numeric_student = User(
            student_no="2025311873",
            name="数字学号学生",
            password_hash="unused",
            role="student",
            status="active",
        )
        db.add(numeric_student)
        db.commit()
        numeric_user_id = numeric_student.id

    legacy_alias = client.post(
        "/api/v1/party/members",
        json={"user_id": 2025311873, **_profile()},
        headers={"X-Test-User": "admin"},
    )
    assert legacy_alias.status_code == 200, legacy_alias.text
    assert legacy_alias.json()["user_id"] == numeric_user_id


def test_status_changes_are_sequential_and_explicitly_audited(party_client) -> None:
    client, session_factory = party_client
    member = _create_member(client, session_factory).json()
    user_id = member["user_id"]
    headers = {"X-Test-User": "admin"}

    skipped = client.put(
        f"/api/v1/party/members/{user_id}/status",
        json={"apply_status": "列为发展对象", "effective_date": "2025-03"},
        headers=headers,
    )
    assert skipped.status_code == 409
    assert skipped.json()["error"]["code"] == "PARTY_STATUS_TRANSITION_INVALID"

    stages = [
        ("确定为积极分子", "2025-02", "入党积极分子"),
        ("列为发展对象", "2025-03", "入党积极分子"),
        ("接受为预备党员", "2025-04", "预备党员"),
        ("转为正式党员", "2026-04", "正式党员"),
    ]
    for status, effective_date, party_type in stages:
        changed = client.put(
            f"/api/v1/party/members/{user_id}/status",
            json={"status": status, "status_date": effective_date},
            headers=headers,
        )
        assert changed.status_code == 200, changed.text
        assert changed.json()["apply_status"] == status
        assert changed.json()["party_type"] == party_type

    with session_factory() as db:
        audits = (
            db.query(AuditLog)
            .filter(
                AuditLog.action == "party_status_change",
                AuditLog.target_id == str(user_id),
            )
            .order_by(AuditLog.id)
            .all()
        )
        assert len(audits) == 4
        detail = json.loads(audits[-1].detail)
        assert detail["from"] == "接受为预备党员"
        assert detail["to"] == "转为正式党员"


def test_status_can_stop_only_with_reason(party_client) -> None:
    client, session_factory = party_client
    user_id = _create_member(client, session_factory, student_no="s3").json()["user_id"]
    headers = {"X-Test-User": "admin"}
    missing = client.put(
        f"/api/v1/party/members/{user_id}/status",
        json={"apply_status": "停止发展"},
        headers=headers,
    )
    assert missing.status_code == 422
    stopped = client.put(
        f"/api/v1/party/members/{user_id}/status",
        json={"apply_status": "停止发展", "stop_reason": "本人申请"},
        headers=headers,
    )
    assert stopped.status_code == 200
    assert stopped.json()["stop_reason"] == "本人申请"
    assert client.put(
        f"/api/v1/party/members/{user_id}/status",
        json={"apply_status": "确定为积极分子", "effective_date": "2025-02"},
        headers=headers,
    ).status_code == 409


def test_csv_import_reports_created_updated_skipped_and_row_errors(party_client) -> None:
    client, session_factory = party_client
    csv_content = (
        "student_no,party_type,branch_name,class_name,grade,apply_date,apply_status,remark\n"
        f"s1,入党积极分子,大数据党支部,{CLASS_NAME},25,2025-01,递交申请,首次\n"
        f"s2,入党积极分子,大数据党支部,{CLASS_NAME},25,2025-01,递交申请,首次\n"
        f"s2,入党积极分子,大数据党支部,{CLASS_NAME},25,2025-01,递交申请,更新\n"
        f"missing,入党积极分子,大数据党支部,{CLASS_NAME},25,2025-01,递交申请,错误\n"
        "teacher,入党积极分子,大数据党支部,未配置班级,25,2025-01,递交申请,错误\n"
    ).encode("utf-8-sig")
    response = client.post(
        "/api/v1/party/members/import",
        files={"file": ("members.csv", csv_content, "text/csv")},
        headers={"X-Test-User": "admin"},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result == {
        "total": 5,
        "created": 2,
        "added": 2,
        "updated": 1,
        "skipped": 0,
        "error_count": 2,
        "errors": result["errors"],
    }
    assert [error["row"] for error in result["errors"]] == [5, 6]
    with session_factory() as db:
        s1 = db.query(User).filter(User.student_no == "s1").one()
        s2 = db.query(User).filter(User.student_no == "s2").one()
        assert s1.party["remark"] == "首次"
        assert s2.party["remark"] == "更新"

    repeated = client.post(
        "/api/v1/party/members/import",
        files={"file": ("one.csv", csv_content.splitlines()[0] + b"\n" + csv_content.splitlines()[1] + b"\n", "text/csv")},
        headers={"X-Test-User": "admin"},
    )
    assert repeated.status_code == 200
    assert repeated.json()["skipped"] == 1


def test_material_upload_permissions_validation_and_soft_delete(party_client) -> None:
    client, session_factory = party_client
    user_id = _create_member(client, session_factory).json()["user_id"]
    path = "/api/v1/party/materials"
    data = {"user_id": str(user_id), "material_type": "思想汇报", "title": "第一季度思想汇报"}

    forbidden = client.post(
        path,
        data=data,
        files={"file": ("思想汇报.pdf", b"%PDF-1.7 content", "application/pdf")},
        headers={"X-Test-User": "s1"},
    )
    assert forbidden.status_code == 403

    invalid = client.post(
        path,
        data=data,
        files={"file": ("思想汇报.txt", b"text", "text/plain")},
        headers={"X-Test-User": "admin"},
    )
    assert invalid.status_code == 400

    oversized = client.post(
        path,
        data=data,
        files={"file": ("large.png", b"x" * (1024 * 1024 + 1), "image/png")},
        headers={"X-Test-User": "admin"},
    )
    assert oversized.status_code == 400

    uploaded = client.post(
        path,
        data=data,
        files={"file": ("思想汇报.pdf", b"%PDF-1.7 content", "application/pdf")},
        headers={"X-Test-User": "admin"},
    )
    assert uploaded.status_code == 200, uploaded.text
    material = uploaded.json()
    assert StorageService.file_exists("party_materials", user_id, material["stored_name"])

    listed = client.get(
        f"/api/v1/party/members/{user_id}/materials",
        headers={"X-Test-User": "admin"},
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    deleted = client.delete(
        f"/api/v1/party/materials/{material['id']}",
        headers={"X-Test-User": "admin"},
    )
    assert deleted.status_code == 200
    assert client.get(
        f"/api/v1/party/members/{user_id}/materials",
        headers={"X-Test-User": "admin"},
    ).json()["total"] == 0
    assert StorageService.file_exists("party_materials", user_id, material["stored_name"])
    with session_factory() as db:
        row = db.get(PartyMaterial, material["id"])
        assert row is not None and row.deleted_at is not None
