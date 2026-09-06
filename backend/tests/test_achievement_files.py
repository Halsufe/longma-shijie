from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

import pytest
from fastapi import Depends, Header
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.api.deps import get_current_user
from backend.app.core.config import settings
from backend.app.core.database import Base, get_db
from backend.app.core.storage import StorageService
from backend.app.models.user import User


def _details() -> dict:
    return {
        "position": "班长",
        "assessment": "优秀",
        "honor_title": "无",
        "start_year": datetime.now().year,
        "start_month": 3,
        "end_year": "进行中",
        "end_month": "进行中",
    }


@pytest.fixture()
def client(tmp_path: Path):
    import backend.app.core.database as db_mod

    previous_engine = db_mod.engine
    previous_session_local = db_mod.SessionLocal
    previous_storage = settings.STORAGE_PATH
    previous_limit = settings.ACHIEVEMENT_FILE_MAX_MB

    db_mod.engine = create_engine(
        f"sqlite:///{tmp_path / 'achievement-files.db'}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    db_mod.SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=db_mod.engine,
        future=True,
    )
    settings.STORAGE_PATH = str(tmp_path / "storage")
    settings.ACHIEVEMENT_FILE_MAX_MB = 1

    from backend.app.main import create_app

    app = create_app()
    Base.metadata.create_all(bind=db_mod.engine)
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
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        db_mod.engine.dispose()
        db_mod.engine = previous_engine
        db_mod.SessionLocal = previous_session_local
        settings.STORAGE_PATH = previous_storage
        settings.ACHIEVEMENT_FILE_MAX_MB = previous_limit


def _upload(
    client: TestClient,
    name: str,
    content: bytes,
    mime: str,
    *,
    user: str = "s1",
):
    return client.post(
        "/api/v1/achievements/files",
        files={"file": (name, content, mime)},
        headers={"X-Test-User": user},
    )


def _create_template(client: TestClient, proofs: list[dict], *, user: str = "s1"):
    return client.post(
        "/api/v1/achievements",
        json={
            "category": "organization",
            "title": "学生组织任职",
            "details": _details(),
            "proofs": proofs,
        },
        headers={"X-Test-User": user},
    )


def test_upload_preview_download_and_permissions(client: TestClient) -> None:
    uploaded = _upload(
        client,
        "任职证明.pdf",
        b"%PDF-1.7 attachment",
        "application/pdf",
    )
    assert uploaded.status_code == 200, uploaded.text
    proof = uploaded.json()
    assert {"id", "name", "path", "size", "mime", "uploaded_at"} <= proof.keys()
    assert proof["name"] == "任职证明.pdf"
    assert proof["path"] == proof["id"]

    created = _create_template(client, [proof])
    assert created.status_code == 200, created.text

    preview = client.get(
        f"/api/v1/achievements/files/{proof['id']}",
        headers={"X-Test-User": "s1"},
    )
    assert preview.status_code == 200
    assert preview.headers["content-type"].startswith("application/pdf")
    assert preview.headers["content-disposition"].startswith("inline;")
    assert preview.content == b"%PDF-1.7 attachment"

    download = client.get(
        f"/api/v1/achievements/files/{proof['id']}?download=true",
        headers={"X-Test-User": "admin"},
    )
    assert download.status_code == 200
    assert download.headers["content-disposition"].startswith("attachment;")

    forbidden = client.get(
        f"/api/v1/achievements/files/{proof['id']}",
        headers={"X-Test-User": "s2"},
    )
    assert forbidden.status_code == 404

    admin_upload = _upload(
        client,
        "管理员材料.png",
        b"admin image",
        "image/png",
        user="admin",
    ).json()
    admin_preview = client.get(
        f"/api/v1/achievements/files/{admin_upload['id']}",
        headers={"X-Test-User": "admin"},
    )
    assert admin_preview.status_code == 200
    assert admin_preview.headers["content-type"].startswith("image/png")


def test_upload_rejects_invalid_and_oversized_files(client: TestClient) -> None:
    invalid = _upload(client, "材料.txt", b"plain text", "text/plain")
    assert invalid.status_code == 400
    assert "仅支持" in invalid.json()["error"]["message"]

    mismatched = _upload(client, "材料.pdf", b"plain text", "text/plain")
    assert mismatched.status_code == 400
    assert "仅支持" in mismatched.json()["error"]["message"]

    oversized = _upload(
        client,
        "大文件.png",
        b"x" * (1024 * 1024 + 1),
        "image/png",
    )
    assert oversized.status_code == 400
    assert "不能超过 1MB" in oversized.json()["error"]["message"]
    assert not any((Path(settings.STORAGE_PATH) / "achievements" / "1").glob("*.png"))


def test_template_requires_owned_proofs_but_legacy_request_remains_compatible(
    client: TestClient,
) -> None:
    missing = _create_template(client, [])
    assert missing.status_code == 422
    assert "至少需要上传 1 份" in missing.json()["error"]["message"]

    first = _upload(client, "证明一.jpg", b"first", "image/jpeg").json()
    second = _upload(client, "证明二.png", b"second", "image/png").json()
    created = _create_template(client, [first, second])
    assert created.status_code == 200, created.text
    assert [proof["id"] for proof in created.json()["proofs"]] == [
        first["id"],
        second["id"],
    ]

    cross_user = _create_template(client, [first], user="s2")
    assert cross_user.status_code == 422
    assert "不存在或无权访问" in cross_user.json()["error"]["message"]

    legacy = client.post(
        "/api/v1/achievements",
        json={
            "category": "organization",
            "title": "旧格式任职成果",
            "achievement_date": "2024-03",
        },
        headers={"X-Test-User": "s1"},
    )
    assert legacy.status_code == 200, legacy.text
    assert legacy.json()["details"] == {}
    assert legacy.json()["proofs"] == []


def test_update_replaces_removes_and_cleans_files(client: TestClient) -> None:
    first = _upload(client, "旧证明.pdf", b"old", "application/pdf").json()
    retained = _upload(client, "保留证明.jpg", b"retained", "image/jpeg").json()
    replacement = _upload(client, "新证明.png", b"new", "image/png").json()
    created = _create_template(client, [first, retained])
    assert created.status_code == 200, created.text

    updated = client.put(
        f"/api/v1/achievements/{created.json()['id']}",
        json={"proofs": [retained, replacement]},
        headers={"X-Test-User": "s1"},
    )
    assert updated.status_code == 200, updated.text
    assert [proof["id"] for proof in updated.json()["proofs"]] == [
        retained["id"],
        replacement["id"],
    ]
    assert not StorageService.file_exists("achievements", 1, first["id"])
    assert StorageService.file_exists("achievements", 1, retained["id"])
    assert StorageService.file_exists("achievements", 1, replacement["id"])

    rejected = client.put(
        f"/api/v1/achievements/{created.json()['id']}",
        json={"proofs": []},
        headers={"X-Test-User": "s1"},
    )
    assert rejected.status_code == 422
    assert StorageService.file_exists("achievements", 1, retained["id"])

    deleted = client.delete(
        f"/api/v1/achievements/{created.json()['id']}",
        headers={"X-Test-User": "s1"},
    )
    assert deleted.status_code == 200
    assert not StorageService.file_exists("achievements", 1, retained["id"])
    assert not StorageService.file_exists("achievements", 1, replacement["id"])
