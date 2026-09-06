import io

import pytest
from fastapi.testclient import TestClient

from backend.app.core.database import Base, SessionLocal, engine
from backend.app.core.security import create_access_token, hash_password
from backend.app.main import app
from backend.app.models.chat import ChatMessage, ChatMessageAttachment
from backend.app.models.school import Assignment, Course, SubmissionAttachment
from backend.app.models.user import User


def _headers(user):
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


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


def test_assignment_attachment_version_binding_and_permissions(client, db):
    admin = User(student_no="TA", name="Admin", password_hash=hash_password("x"), role="admin", status="active")
    student = User(student_no="TS", name="Student", password_hash=hash_password("x"), role="student", status="active")
    other = User(student_no="TO", name="Other", password_hash=hash_password("x"), role="student", status="active")
    db.add_all([admin, student, other]); db.commit()
    course = Course(name="Course", created_by=admin.id); db.add(course); db.commit()
    assignment = Assignment(course_id=course.id, title="Work", created_by=admin.id, status="published")
    db.add(assignment); db.commit()
    response = client.post(f"/api/v1/assignments/{assignment.id}/attachments", headers=_headers(admin), files=[("files", ("guide.txt", io.BytesIO(b"guide"), "text/plain"))])
    assert response.status_code == 200
    response = client.post(f"/api/v1/assignments/{assignment.id}/submit-files", headers=_headers(student), data={"content": "v1"}, files=[("files", ("answer.txt", io.BytesIO(b"answer"), "text/plain"))])
    assert response.status_code == 200 and response.json()["version"] == 1
    attachment_id = response.json()["attachments"][0]["id"]
    assert db.query(SubmissionAttachment).filter(SubmissionAttachment.version == 1).count() == 1
    assert client.get(f"/api/v1/submissions/attachments/{attachment_id}/download", headers=_headers(other)).status_code == 403


def test_chat_regenerate_only_latest_assistant(client, db, monkeypatch):
    user = User(student_no="TC", name="Chat", password_hash=hash_password("x"), role="student", status="active")
    db.add(user); db.commit()
    session = client.post("/api/v1/chat/sessions", headers=_headers(user), json={"title": "Test"}).json()
    first = ChatMessage(session_id=session["id"], role="assistant", content="old")
    last = ChatMessage(session_id=session["id"], role="assistant", content="last")
    db.add_all([first, last]); db.commit()

    class Adapter:
        async def chat(self, messages, system_prompt=""):
            return "new"

    monkeypatch.setattr("backend.app.services.chat_service.get_adapter", lambda: Adapter())
    assert client.post(f"/api/v1/chat/sessions/{session['id']}/messages/{first.id}/regenerate", headers=_headers(user)).status_code == 400
    response = client.post(f"/api/v1/chat/sessions/{session['id']}/messages/{last.id}/regenerate", headers=_headers(user))
    assert response.status_code == 200 and response.json()["content"] == "new" and response.json()["regenerated_at"]


def test_chat_multipart_attachment_and_owner_isolation(client, db, monkeypatch):
    user = User(student_no="TC1", name="Chat One", password_hash=hash_password("x"), role="student", status="active")
    other = User(student_no="TC2", name="Chat Two", password_hash=hash_password("x"), role="student", status="active")
    db.add_all([user, other]); db.commit()
    session = client.post("/api/v1/chat/sessions", headers=_headers(user), json={"title": "Files"}).json()

    class Adapter:
        name = "test"

        async def chat_stream(self, messages, system_prompt=""):
            assert "附件正文" in system_prompt
            yield "收到附件"

    monkeypatch.setattr("backend.app.services.chat_service.get_adapter", lambda: Adapter())
    response = client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages",
        headers=_headers(user),
        data={"content": "请总结", "rag_scope": "none"},
        files=[("files", ("notes.txt", io.BytesIO("附件正文".encode()), "text/plain"))],
    )
    assert response.status_code == 200 and "收到附件" in response.text
    attachment = db.query(ChatMessageAttachment).one()
    message = db.query(ChatMessage).filter(ChatMessage.id == attachment.message_id).one()
    assert client.get(f"/api/v1/chat/messages/{message.id}/attachments", headers=_headers(user)).status_code == 200
    assert client.get(f"/api/v1/chat/attachments/{attachment.id}/download", headers=_headers(other)).status_code == 404


def test_chat_regenerate_sse_compatibility(client, db, monkeypatch):
    user = User(student_no="TCS", name="Chat SSE", password_hash=hash_password("x"), role="student", status="active")
    db.add(user); db.commit()
    session = client.post("/api/v1/chat/sessions", headers=_headers(user), json={"title": "SSE"}).json()
    message = ChatMessage(session_id=session["id"], role="assistant", content="old")
    db.add(message); db.commit()

    class Adapter:
        async def chat(self, messages, system_prompt=""):
            return "new-sse"

    monkeypatch.setattr("backend.app.services.chat_service.get_adapter", lambda: Adapter())
    response = client.post(
        f"/api/v1/chat/sessions/{session['id']}/messages/{message.id}/regenerate?stream=true",
        headers={**_headers(user), "Accept": "text/event-stream"},
    )
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/event-stream")
    assert "new-sse" in response.text
