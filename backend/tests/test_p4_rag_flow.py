"""
P4 知识库与 RAG 全流程集成测试
覆盖：上传 → 解析 → 检索 → RAG 接入对话
"""
import io
import os
import sys
import json
import tempfile

# 确保项目根目录在 path 中
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.database import Base, get_db
from backend.app.core.security import hash_password
from backend.app.models.user import User
from backend.app.models.chat import ChatSession, ChatMessage
from backend.app.models.file import KnowledgeFile, FileChunk


def _setup_app(tmp_storage: str):
    """构建使用内存数据库 + 临时存储的 app 实例"""
    # 覆盖配置：内存 DB + 临时存储路径
    from backend.app.core import config as cfg
    cfg.settings.DB_URL = "sqlite:///:memory:"
    cfg.settings.STORAGE_PATH = tmp_storage
    cfg.settings.AI_API_KEY = ""  # 使用 mock adapter

    # 重新构建 engine（因为 lru_cache 的 settings 已加载）
    from backend.app.core import database as db_mod
    db_mod.engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        future=True,
        poolclass=StaticPool,
    )
    db_mod.SessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=db_mod.engine, future=True
    )

    # 创建所有表
    Base.metadata.create_all(bind=db_mod.engine)

    # 重新导入 app（确保使用新 engine）
    from backend.app.main import create_app
    app = create_app()

    # 依赖覆盖
    def override_get_db():
        db = db_mod.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return app, db_mod


def _seed_users(db):
    """创建测试用户：管理员 + 普通用户"""
    admin = User(
        student_no="admin001",
        name="管理员",
        password_hash=hash_password("Admin@123"),
        role="admin",
        status="active",
    )
    user = User(
        student_no="2025001",
        name="张三",
        password_hash=hash_password("User@123"),
        role="student",
        status="active",
    )
    admin.profile = {"class_id": 1}
    user.profile = {"class_id": 1}
    db.add(admin)
    db.add(user)
    db.commit()
    db.refresh(admin)
    db.refresh(user)
    return admin, user


def _login(client, student_no: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"student_no": student_no, "password": password},
    )
    assert resp.status_code == 200, f"登录失败: {resp.text}"
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_full_p4_flow():
    """端到端测试：上传 → 解析 → 检索 → RAG 对话"""
    with tempfile.TemporaryDirectory() as tmp_storage:
        app, db_mod = _setup_app(tmp_storage)
        client = TestClient(app)

        # 种子用户
        db = db_mod.SessionLocal()
        try:
            admin, user = _seed_users(db)
        finally:
            db.close()

        admin_token = _login(client, "admin001", "Admin@123")
        user_token = _login(client, "2025001", "User@123")

        # ============================================================
        # 1. 个人知识库：上传 TXT 文件
        # ============================================================
        txt_content = (
            "龙马视界项目是一个基于大语言模型的智能教学助手。\n"
            "该项目支持知识库管理、文档检索和智能问答。\n"
            "RAG 技术能够结合外部知识库提供准确答案。\n"
            "FastAPI 是后端框架，使用 SQLAlchemy 作为 ORM。"
        )
        files = {"file": ("项目介绍.txt", io.BytesIO(txt_content.encode("utf-8")), "text/plain")}
        resp = client.post(
            "/api/v1/knowledge/upload",
            files=files,
            data={"tag": "项目文档"},
            headers=_auth(user_token),
        )
        assert resp.status_code == 200, f"个人上传失败: {resp.text}"
        personal_file = resp.json()
        assert personal_file["parse_status"] == "ready", f"解析状态异常: {personal_file['parse_status']}"
        assert personal_file["scope"] == "personal"
        print(f"[OK] 1. 个人知识库上传+解析: {personal_file['original_name']} -> {personal_file['parse_status']}")

        # ============================================================
        # 2. 班级知识库：管理员上传
        # ============================================================
        class_content = (
            "数据结构课程大纲：第一章线性表，第二章栈和队列，第三章树与二叉树。\n"
            "考试重点包括二叉树遍历、图的搜索算法、动态规划。\n"
            "推荐教材《数据结构（C语言版）》严蔚敏编著。"
        )
        files = {"file": ("数据结构大纲.txt", io.BytesIO(class_content.encode("utf-8")), "text/plain")}
        resp = client.post(
            "/api/v1/class-knowledge/upload",
            files=files,
            data={"tag": "课程资料"},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200, f"班级上传失败: {resp.text}"
        class_file = resp.json()
        assert class_file["parse_status"] == "ready"
        print(f"[OK] 2. 班级知识库上传+解析(管理员): {class_file['original_name']}")

        # 普通用户上传班级知识库应被拒绝
        files = {"file": ("x.txt", io.BytesIO(b"x"), "text/plain")}
        resp = client.post(
            "/api/v1/class-knowledge/upload",
            files=files,
            headers=_auth(user_token),
        )
        assert resp.status_code == 403, f"权限校验失效: {resp.status_code}"
        print("[OK] 2b. 普通用户无法上传班级知识库(权限隔离)")

        # ============================================================
        # 3. 列表 + 详情 + 配额
        # ============================================================
        resp = client.get("/api/v1/knowledge/files", headers=_auth(user_token))
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        print("[OK] 3a. 个人知识库列表")

        resp = client.get("/api/v1/class-knowledge/files", headers=_auth(user_token))
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        print("[OK] 3b. 班级知识库列表(普通用户可查)")

        resp = client.get("/api/v1/knowledge/quota", headers=_auth(user_token))
        assert resp.status_code == 200
        quota = resp.json()
        assert quota["used_bytes"] > 0
        print(f"[OK] 3c. 配额查询: 已用 {quota['used_mb']}MB / {quota['quota_mb']}MB")

        # ============================================================
        # 4. 创建会话 + RAG 对话（命中个人知识库）
        # ============================================================
        resp = client.post(
            "/api/v1/chat/sessions",
            json={"title": "RAG 测试会话"},
            headers=_auth(user_token),
        )
        assert resp.status_code == 200
        session_id = resp.json()["id"]
        print(f"[OK] 4a. 创建会话: id={session_id}")

        # 非流式：rag_scope=all，提问命中知识库内容
        resp = client.post(
            f"/api/v1/chat/sessions/{session_id}/messages/simple",
            json={"content": "龙马视界项目用的是什么后端框架？", "rag_scope": "all"},
            headers=_auth(user_token),
        )
        assert resp.status_code == 200, f"RAG 对话失败: {resp.text}"
        result = resp.json()
        assert result["ai_message"]["has_citations"] is True, "应包含引用来源"
        print(f"[OK] 4b. RAG 对话命中知识库, has_citations={result['ai_message']['has_citations']}")
        print(f"      skill={result['ai_message']['skill']}, model={result['ai_message']['model']}")

        # ============================================================
        # 5. RAG scope 隔离：personal 命中个人，class 命中班级
        # ============================================================
        resp = client.post(
            f"/api/v1/chat/sessions/{session_id}/messages/simple",
            json={"content": "数据结构考试重点有哪些？", "rag_scope": "class"},
            headers=_auth(user_token),
        )
        assert resp.status_code == 200
        assert resp.json()["ai_message"]["has_citations"] is True
        print("[OK] 5a. rag_scope=class 命中班级知识库")

        resp = client.post(
            f"/api/v1/chat/sessions/{session_id}/messages/simple",
            json={"content": "龙马视界项目是什么？", "rag_scope": "personal"},
            headers=_auth(user_token),
        )
        assert resp.status_code == 200
        assert resp.json()["ai_message"]["has_citations"] is True
        print("[OK] 5b. rag_scope=personal 命中个人知识库")

        # ============================================================
        # 6. rag_scope=none 不检索
        # ============================================================
        resp = client.post(
            f"/api/v1/chat/sessions/{session_id}/messages/simple",
            json={"content": "龙马视界项目是什么？", "rag_scope": "none"},
            headers=_auth(user_token),
        )
        assert resp.status_code == 200
        assert resp.json()["ai_message"]["has_citations"] is False, "none 模式不应有引用"
        print("[OK] 6. rag_scope=none 不检索知识库")

        # ============================================================
        # 7. 无效 rag_scope 报错
        # ============================================================
        resp = client.post(
            f"/api/v1/chat/sessions/{session_id}/messages/simple",
            json={"content": "test", "rag_scope": "invalid"},
            headers=_auth(user_token),
        )
        assert resp.status_code == 400, f"无效 scope 应返回 400: {resp.status_code}"
        print("[OK] 7. 无效 rag_scope 返回 400")

        # ============================================================
        # 8. 流式接口（SSE）含 rag 事件
        # ============================================================
        with client.stream(
            "POST",
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"content": "FastAPI 是什么？", "rag_scope": "all"},
            headers=_auth(user_token),
        ) as stream:
            assert stream.status_code == 200
            events = []
            for line in stream.iter_lines():
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))
        event_types = [e["type"] for e in events]
        assert "rag" in event_types, f"流式应包含 rag 事件: {event_types}"
        assert "done" in event_types, f"流式应包含 done 事件: {event_types}"
        print(f"[OK] 8. 流式 SSE 事件类型: {event_types}")

        # ============================================================
        # 9. 删除文件（软删除 + chunks 清理）
        # ============================================================
        resp = client.delete(
            f"/api/v1/knowledge/files/{personal_file['id']}",
            headers=_auth(user_token),
        )
        assert resp.status_code == 200
        print("[OK] 9. 删除个人文件(软删除)")

        # 删除后检索不再命中
        resp = client.get("/api/v1/knowledge/files", headers=_auth(user_token))
        assert resp.json()["total"] == 0
        print("[OK] 9b. 删除后列表为空")

        print("\n========== P4 全流程测试通过 ==========")


def test_chat_quota_and_request_endpoints_enforce_user_boundaries():
    with tempfile.TemporaryDirectory() as tmp_storage:
        app, db_mod = _setup_app(tmp_storage)
        client = TestClient(app)
        db = db_mod.SessionLocal()
        try:
            admin, user = _seed_users(db)
            other = User(
                student_no="2025002", name="李四", password_hash=hash_password("User@123"),
                role="student", status="active",
            )
            db.add(other)
            db.commit()
            db.refresh(other)
            from backend.app.repositories.chat_repo import ChatRepository
            session = ChatRepository.create_session(db, user_id=other.id, title="other")
            from backend.app.models.chat_request import ChatRequest
            request_row = ChatRequest(
                request_id="owned-by-other", session_id=session.id, user_id=other.id,
                idempotency_key="owned-by-other", model="deepseek-v4-flash",
                knowledge_scope="personal", status="failed", input_content="hello",
            )
            db.add(request_row)
            db.commit()
            user_id, other_id = user.id, other.id
        finally:
            db.close()

        user_token = _login(client, "2025001", "User@123")
        other_token = _login(client, "2025002", "User@123")
        user_headers = _auth(user_token)

        assert client.get("/api/v1/admin/chat/quota-policies", headers=user_headers).status_code == 403
        assert client.get("/api/v1/admin/chat/usage", headers=user_headers).status_code == 403
        assert client.get("/api/v1/admin/chat/user-quotas", headers=user_headers).status_code == 403
        assert client.put(
            "/api/v1/admin/chat/quota-policies/student",
            json={"daily_limit": 100, "reason": "no"}, headers=user_headers,
        ).status_code == 403

        assert client.get("/api/v1/chat/requests/owned-by-other", headers=user_headers).status_code == 404
        assert client.post("/api/v1/chat/requests/owned-by-other/retry", headers=user_headers).status_code == 404
        assert client.post("/api/v1/chat/requests/owned-by-other/continue", headers=user_headers).status_code == 404

        assert client.get("/api/v1/chat/requests/owned-by-other", headers=_auth(other_token)).status_code == 200

        admin_token = _login(client, "admin001", "Admin@123")
        policies = client.get("/api/v1/admin/chat/quota-policies", headers=_auth(admin_token))
        assert policies.status_code == 200
        assert {item["role"] for item in policies.json()} == {"admin", "alumni", "student", "teacher"}
        user_quotas = client.get("/api/v1/admin/chat/user-quotas", headers=_auth(admin_token))
        assert user_quotas.status_code == 200
        assert {item["user_id"] for item in user_quotas.json()["items"]} >= {user_id, other_id}
        override = client.put(
            f"/api/v1/admin/users/{user_id}/chat-quota",
            json={"daily_limit": 1200, "reason": "测试临时额度"},
            headers=_auth(admin_token),
        )
        assert override.status_code == 200
        assert override.json()["daily_limit"] == 1200


if __name__ == "__main__":
    test_full_p4_flow()
