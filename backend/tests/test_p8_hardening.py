"""
P8 硬化测试：Refresh Token/会话管理、幂等键、文件清理、日志脱敏、分页上限、限流
"""
import io
import os
import sys
import tempfile
import logging

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


def _setup_app(tmp_storage: str):
    from backend.app.core import config as cfg

    cfg.settings.DB_URL = "sqlite:///:memory:"
    cfg.settings.STORAGE_PATH = tmp_storage
    cfg.settings.AI_API_KEY = ""
    cfg.settings.MCP_SERVICE_TOKEN = "test-mcp-token"
    cfg.settings.ENV = "test"  # 禁用 cleanup loop 自动启动
    cfg.settings.API_RATE_LIMIT = 100000  # 主流程不限流

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
    Base.metadata.create_all(bind=db_mod.engine)

    from backend.app.main import create_app

    app = create_app()

    def override_get_db():
        db = db_mod.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return app, db_mod


def _seed_users(db):
    admin = User(
        student_no="admin001", name="管理员", password_hash=hash_password("Admin@123"),
        role="admin", status="active",
    )
    s1 = User(
        student_no="2025001", name="张三", password_hash=hash_password("User@123"),
        role="student", status="active",
    )
    s2 = User(
        student_no="2025002", name="李四", password_hash=hash_password("User@123"),
        role="student", status="active",
    )
    db.add_all([admin, s1, s2])
    db.commit()
    for u in (admin, s1, s2):
        db.refresh(u)
    return admin, s1, s2


def _login(client, student_no, password):
    r = client.post("/api/v1/auth/login", json={"student_no": student_no, "password": password})
    assert r.status_code == 200, f"登录失败: {r.text}"
    return r.json()


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_p8_hardening():
    with tempfile.TemporaryDirectory() as tmp:
        app, db_mod = _setup_app(tmp)
        client = TestClient(app)
        db = db_mod.SessionLocal()
        try:
            admin, s1, s2 = _seed_users(db)
        finally:
            db.close()

        # ========== P8-1&2: Refresh Token + 会话管理 ==========
        login_resp = _login(client, "2025002", "User@123")
        access = login_resp["access_token"]
        refresh = login_resp["refresh_token"]
        assert refresh, "登录应返回 refresh_token"
        print("[OK] P8-1 登录返回 access + refresh")

        # access 可用
        r = client.get("/api/v1/users/me", headers=_auth(access))
        assert r.status_code == 200, r.text
        print("[OK] P8-1a access token 可访问业务接口")

        # access 不能当 refresh 用
        r = client.post("/api/v1/auth/refresh", json={"refresh_token": access})
        assert r.status_code == 401, "access token 不应能刷新"
        print("[OK] P8-1b access token 不能用于 /refresh")

        # refresh 换新 access（旋转）
        r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
        assert r.status_code == 200, r.text
        new_access = r.json()["access_token"]
        new_refresh = r.json()["refresh_token"]
        assert new_access != access and new_refresh != refresh
        print("[OK] P8-1c refresh 旋转成功（新 access + 新 refresh）")

        # 旧 refresh 已撤销
        r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
        assert r.status_code == 401, "旧 refresh 应失效"
        # 旧 access 也应失效（会话已撤销）
        r = client.get("/api/v1/users/me", headers=_auth(access))
        assert r.status_code == 401, "旧 access 应随会话撤销失效"
        print("[OK] P8-1d 旧 refresh + 旧 access 均失效")

        # 新 access 可用
        r = client.get("/api/v1/users/me", headers=_auth(new_access))
        assert r.status_code == 200
        print("[OK] P8-1e 新 access 可用")

        # 设备会话列表
        r = client.get("/api/v1/users/me/sessions", headers=_auth(new_access))
        assert r.status_code == 200 and r.json()["total"] >= 1, r.text
        current = [s for s in r.json()["items"] if s["is_current"]]
        assert len(current) == 1, "应有且仅有一个当前会话"
        print(f"[OK] P8-2a 设备会话列表: {r.json()['total']} 个活跃会话")

        # 撤销当前会话 → access 立即失效
        sid = current[0]["id"]
        r = client.delete(f"/api/v1/users/me/sessions/{sid}", headers=_auth(new_access))
        assert r.status_code == 200, r.text
        r = client.get("/api/v1/users/me", headers=_auth(new_access))
        assert r.status_code == 401, "撤销会话后 access 应立即失效"
        print("[OK] P8-2b 撤销会话后 access 立即失效")

        # ========== P8-3: Idempotency-Key ==========
        admin_login = _login(client, "admin001", "Admin@123")
        admin_t = admin_login["access_token"]
        idem_h = {**_auth(admin_t), "Idempotency-Key": "course-abc-001"}
        payload = {"name": "幂等测试课程", "teacher": "测试", "semester": "2025-2026-1"}
        r1 = client.post("/api/v1/courses", json=payload, headers=idem_h)
        assert r1.status_code == 200, r1.text
        r2 = client.post("/api/v1/courses", json=payload, headers=idem_h)
        assert r2.status_code == 200 and r1.json() == r2.json(), "重复提交应返回相同响应"
        assert r2.headers.get("X-Idempotent-Replay") == "true", "应标记幂等重放"
        print("[OK] P8-3 Idempotency-Key 重复提交返回缓存响应 + X-Idempotent-Replay")

        # 不同 key 正常创建
        idem_h2 = {**_auth(admin_t), "Idempotency-Key": "course-abc-002"}
        r3 = client.post("/api/v1/courses", json=payload, headers=idem_h2)
        assert r3.status_code == 200 and r3.json()["id"] != r1.json()["id"]
        print("[OK] P8-3b 不同 Idempotency-Key 正常创建新资源")

        # ========== P8-4: 文件清理 worker ==========
        db = db_mod.SessionLocal()
        try:
            from backend.app.repositories.file_repo import FileRepository
            from backend.app.core.storage import StorageService
            from backend.app.workers.file_cleanup import run_cleanup

            s1_t = _login(client, "2025001", "User@123")["access_token"]
            r = client.post(
                "/api/v1/knowledge/upload",
                files={"file": ("cleanup.txt", io.BytesIO("待清理内容".encode()), "text/plain")},
                headers=_auth(s1_t),
            )
            assert r.status_code == 200, r.text
            fid = r.json()["id"]

            # 软删除
            r = client.delete(f"/api/v1/knowledge/files/{fid}", headers=_auth(s1_t))
            assert r.status_code == 200, r.text

            kf = FileRepository.get_by_id(db, fid, include_deleted=True)
            assert kf is not None, "软删后记录应保留"
            phys_path = StorageService.get_file_path("personal", s1.id, kf.stored_name)
            assert os.path.exists(phys_path), "软删后物理文件应保留（7天恢复期）"

            # 手动清理（retention=0 → 立即物理删除）
            n = run_cleanup(db, retention_days=0)
            assert n >= 1, "应清理至少 1 个文件"
            assert not os.path.exists(phys_path), "清理后物理文件应删除"
            assert FileRepository.get_by_id(db, fid, include_deleted=True) is None, "清理后记录应硬删除"
            print(f"[OK] P8-4 文件清理: 软删→保留物理文件→run_cleanup(0天)→物理删+硬删 ({n}个)")
        finally:
            db.close()

        # ========== P8-5: 日志脱敏 ==========
        from backend.app.core.logging import SanitizingFilter

        buf = io.StringIO()
        h = logging.StreamHandler(buf)
        h.addFilter(SanitizingFilter())
        tlog = logging.getLogger("test_sanitizer_p8")
        tlog.setLevel(logging.INFO)
        tlog.addHandler(h)
        tlog.propagate = False
        tlog.info("Login attempt password=secret123 api_key=sk-xyz token=abc.def.ghi")
        tlog.info("Authorization: Bearer abcd1234token")
        out = buf.getvalue()
        assert "secret123" not in out, f"密码应脱敏: {out}"
        assert "sk-xyz" not in out, f"api_key 应脱敏: {out}"
        assert "abc.def.ghi" not in out, f"token 应脱敏: {out}"
        assert "abcd1234token" not in out, f"Bearer token 应脱敏: {out}"
        assert "***" in out, f"应包含脱敏标记: {out}"
        print("[OK] P8-5 日志脱敏: password/api_key/token/Bearer → ***")

        # ========== P8-6: 分页上限 ==========
        from backend.app.core.pagination import normalize_page_size

        assert normalize_page_size(500) == 100, "page_size>100 应截断为 100"
        assert normalize_page_size(0) == 1
        assert normalize_page_size(None) == 20
        assert normalize_page_size(50) == 50
        # 集成：page_size=500 不报错
        r = client.get("/api/v1/admin/users?page_size=500", headers=_auth(admin_t))
        assert r.status_code == 200, r.text
        print("[OK] P8-6 分页上限: page_size=500→100，接口正常")

        # ========== P8-9: 通用限流 ==========
        from backend.app.core.rate_limit import _limiter
        from backend.app.core import config as cfg

        _limiter._hits.clear()
        old_limit = cfg.settings.API_RATE_LIMIT
        cfg.settings.API_RATE_LIMIT = 3
        try:
            codes = [client.get("/").status_code for _ in range(5)]
            assert 429 in codes, f"超限应返回 429: {codes}"
            print(f"[OK] P8-9 通用限流: limit=3 时第4+次返回 429（codes={codes}）")
        finally:
            cfg.settings.API_RATE_LIMIT = old_limit
            _limiter._hits.clear()

        print("\n========== P8 硬化测试通过 ==========")


if __name__ == "__main__":
    test_p8_hardening()
