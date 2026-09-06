import io
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from backend.app.core.database import Base, SessionLocal, engine
from backend.app.core.security import create_access_token, hash_password
from backend.app.main import app
from backend.app.models.user import User
from backend.app.models.user_session import UserSession
from backend.app.core.database import local_now


@pytest.fixture
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


def test_admin_import_preview_classifies_and_hash_binds(client, db):
    admin = User(student_no="IA", name="Admin", password_hash=hash_password("x"), role="admin", status="active")
    existing = User(student_no="IU", name="Old", password_hash=hash_password("x"), role="student", status="active")
    deleted = User(student_no="ID", name="Deleted", password_hash=hash_password("x"), role="student", status="disabled")
    deleted.deleted_at = local_now()
    db.add_all([admin, existing, deleted]); db.commit()
    csv = "学号,姓名,角色\nIU,Updated,student\nID,Restored,student\nIN,New,student\nIN,Duplicate,student\n"
    response = client.post("/api/v1/admin/users/import/preview", headers=_headers(admin), files={"file": ("users.csv", io.BytesIO(csv.encode()), "text/csv")})
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["update"] == 1 and payload["summary"]["restore"] == 1
    assert payload["summary"]["skip"] == 1 and payload["confirmation_token"]
    bad = client.post(f"/api/v1/admin/users/import/confirm?confirmation_token={payload['confirmation_token']}", headers=_headers(admin), files={"file": ("users.csv", io.BytesIO((csv + "x").encode()), "text/csv")})
    assert bad.status_code == 400
    confirmed = client.post(f"/api/v1/admin/users/import/confirm?confirmation_token={payload['confirmation_token']}", headers=_headers(admin), files={"file": ("users.csv", io.BytesIO(csv.encode()), "text/csv")})
    assert confirmed.status_code == 200 and confirmed.json()["created"] == 1


def test_admin_export_and_activity_are_filtered_and_deduplicated(client, db):
    admin = User(student_no="EA", name="Admin", password_hash=hash_password("x"), role="admin", status="active")
    student = User(student_no="ES", name="Student", password_hash=hash_password("x"), role="student", status="active")
    db.add_all([admin, student]); db.commit()
    now = local_now()
    for suffix in ("a", "b"):
        db.add(UserSession(user_id=student.id, device_id=suffix, jti=f"j{suffix}", refresh_token_hash="x", expires_at=now + timedelta(days=1), last_active_at=now))
    db.commit()
    exported = client.get("/api/v1/admin/users/export?role=student", headers=_headers(admin))
    assert exported.status_code == 200 and exported.content.startswith(b"\xef\xbb\xbf") and b"ES" in exported.content
    activity = client.get("/api/v1/admin/stats/activity?days=1", headers=_headers(admin))
    assert activity.status_code == 200 and activity.json()["today_dau"] == 1
    business = client.get("/api/v1/admin/stats/business?category=competition", headers=_headers(admin))
    assert business.status_code == 200
    assert "projects" not in business.json()
