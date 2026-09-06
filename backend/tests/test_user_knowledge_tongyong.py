import io

import pytest
from fastapi.testclient import TestClient

from backend.app.core.database import Base, SessionLocal, engine
from backend.app.core.security import create_access_token, hash_password
from backend.app.main import app
from backend.app.models.audit import AuditLog
from backend.app.models.notification import Notification
from backend.app.models.user import User


def _token(user):
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


@pytest.fixture
def db_session():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _users(db):
    student = User(student_no="D1S", name="Student", password_hash=hash_password("x"), role="student", status="active")
    other = User(student_no="D1O", name="Other", password_hash=hash_password("x"), role="student", status="active")
    admin = User(student_no="D1A", name="Admin", password_hash=hash_password("x"), role="admin", status="active")
    db.add_all([student, other, admin])
    db.commit()
    return student, other, admin


def test_profile_validation_and_alumni_flow(client, db_session):
    student, _, admin = _users(db_session)
    response = client.put("/api/v1/users/me", headers=_token(student), json={"profile": {"major": "CS", "interests": "AI，Robotics", "grade": "2026", "unknown": "ignored"}})
    assert response.status_code == 200
    assert response.json()["profile"] == {"major": "CS", "interests": ["AI", "Robotics"], "grade": "2026"}
    response = client.put("/api/v1/users/me", headers=_token(student), json={"profile": {"development_plan": "x" * 2001}})
    assert response.status_code == 400

    response = client.post("/api/v1/users/me/alumni-request", headers=_token(student), json={"graduation_year": 2025})
    assert response.status_code == 200
    request_id = response.json()["id"]
    assert client.post("/api/v1/users/me/alumni-request", headers=_token(student), json={"graduation_year": 2025}).status_code == 400
    response = client.post(f"/api/v1/admin/users/alumni-requests/{request_id}/approve", headers=_token(admin))
    assert response.status_code == 200 and response.json()["role"] == "alumni"
    assert db_session.query(Notification).filter(Notification.user_id == student.id, Notification.ref_type == "alumni_request").count()
    assert db_session.query(AuditLog).filter(AuditLog.action == "alumni_request.approve").count()


def test_personal_folders_permissions_preview_and_class_versions(client, db_session):
    student, other, admin = _users(db_session)
    response = client.post("/api/v1/knowledge/folders", headers=_token(student), json={"name": "Notes"})
    assert response.status_code == 200
    folder_id = response.json()["id"]
    assert client.post("/api/v1/knowledge/folders", headers=_token(student), json={"name": "Notes"}).status_code == 400
    upload = client.post("/api/v1/knowledge/upload", headers=_token(student), files={"file": ("x.txt", io.BytesIO(b"<script>alert(1)</script>"), "text/plain")}, data={"folder_id": str(folder_id)})
    assert upload.status_code == 200
    file_id = upload.json()["id"]
    assert client.delete(f"/api/v1/knowledge/folders/{folder_id}", headers=_token(student)).status_code == 400
    preview = client.get(f"/api/v1/knowledge/files/{file_id}/preview", headers=_token(student))
    assert preview.status_code == 200 and "<script>" not in preview.json()["content"]
    assert client.get(f"/api/v1/knowledge/files/{file_id}/preview", headers=_token(other)).status_code == 404

    uploaded = client.post("/api/v1/class-knowledge/upload", headers=_token(admin), files={"file": ("v1.txt", io.BytesIO(b"one"), "text/plain")})
    class_id = uploaded.json()["id"]
    replaced = client.post(f"/api/v1/class-knowledge/files/{class_id}/replace", headers=_token(admin), files={"file": ("v2.txt", io.BytesIO(b"two"), "text/plain")})
    assert replaced.status_code == 200 and replaced.json()["version"] == 2
    history = client.get(f"/api/v1/class-knowledge/files/{class_id}/versions", headers=_token(student)).json()
    assert history[0]["version"] == 1
