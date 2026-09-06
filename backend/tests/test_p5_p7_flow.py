"""
P5-P7 集成测试：课程与作业 / Skills 与 MCP / 管理与审计
"""
import io
import os
import sys
import tempfile

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
    admin = User(student_no="admin001", name="管理员", password_hash=hash_password("Admin@123"),
                 role="admin", status="active")
    s1 = User(student_no="2025001", name="张三", password_hash=hash_password("User@123"),
              role="student", status="active")
    s2 = User(student_no="2025002", name="李四", password_hash=hash_password("User@123"),
              role="student", status="active")
    db.add_all([admin, s1, s2])
    db.commit()
    for u in (admin, s1, s2):
        db.refresh(u)
    return admin, s1, s2


def _login(client, student_no, password):
    r = client.post("/api/v1/auth/login", json={"student_no": student_no, "password": password})
    assert r.status_code == 200, f"登录失败: {r.text}"
    return r.json()["access_token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_p5_p7_flow():
    with tempfile.TemporaryDirectory() as tmp:
        app, db_mod = _setup_app(tmp)
        client = TestClient(app)
        db = db_mod.SessionLocal()
        try:
            admin, s1, s2 = _seed_users(db)
        finally:
            db.close()

        admin_t = _login(client, "admin001", "Admin@123")
        s1_t = _login(client, "2025001", "User@123")

        # ========== P5: 课程 ==========
        r = client.post("/api/v1/courses", json={"name": "数据结构", "teacher": "王老师", "semester": "2025-2026-1"}, headers=_auth(admin_t))
        assert r.status_code == 200, r.text
        course_id = r.json()["id"]
        print(f"[OK] P5-1 创建课程: id={course_id}")

        r = client.put(f"/api/v1/courses/{course_id}/schedules", json=[
            {"weekday": 1, "start_period": 1, "end_period": 2, "location": "A101", "weeks_pattern": "1-16"},
            {"weekday": 3, "start_period": 3, "end_period": 4, "location": "A102"},
        ], headers=_auth(admin_t))
        assert r.status_code == 200 and len(r.json()) == 2, r.text
        print("[OK] P5-2 设置课程时间安排(2条)")

        # ========== P5: 作业 ==========
        r = client.post("/api/v1/assignments", json={
            "course_id": course_id, "title": "实验一：链表实现",
            "description": "实现单链表的基本操作", "total_score": 100,
        }, headers=_auth(admin_t))
        assert r.status_code == 200, r.text
        aid = r.json()["id"]
        assert r.json()["status"] == "draft"
        print(f"[OK] P5-3 创建作业(draft): id={aid}")

        # 学生看不到 draft
        r = client.get("/api/v1/assignments", headers=_auth(s1_t))
        assert r.json()["total"] == 0, "学生不应看到 draft 作业"
        print("[OK] P5-4 学生无法看到未发布作业")

        # 发布 + 通知（幂等）
        r = client.post(f"/api/v1/assignments/{aid}/publish", headers=_auth(admin_t))
        assert r.status_code == 200 and r.json()["status"] == "published"
        # 学生现在能看到
        r = client.get("/api/v1/assignments", headers=_auth(s1_t))
        assert r.json()["total"] == 1
        print("[OK] P5-5 发布作业，学生可见")

        # 学生应收到通知（2个学生）
        r = client.get("/api/v1/notifications", headers=_auth(s1_t))
        assert r.json()["total"] == 1 and r.json()["unread_count"] == 1, r.text
        print("[OK] P5-6 学生收到新作业通知")

        # 再次发布（幂等，不应重复通知）
        client.post(f"/api/v1/assignments/{aid}/publish", headers=_auth(admin_t))
        r = client.get("/api/v1/notifications", headers=_auth(s1_t))
        assert r.json()["total"] == 1, "幂等：重复发布不应产生重复通知"
        print("[OK] P5-7 通知幂等（重复发布不重复通知）")

        # ========== P5: 提交 + 版本 ==========
        r = client.post(f"/api/v1/assignments/{aid}/submit", json={"content": "第一版提交"}, headers=_auth(s1_t))
        assert r.status_code == 200 and r.json()["version"] == 1, r.text
        r = client.post(f"/api/v1/assignments/{aid}/submit", json={"content": "第二版修改"}, headers=_auth(s1_t))
        assert r.json()["version"] == 2 and r.json()["is_update"] is True, r.text
        print("[OK] P5-8 提交版本管理(v1→v2)")

        sub = client.get(f"/api/v1/assignments/{aid}/submission", headers=_auth(s1_t))
        assert sub.json()["content"] == "第二版修改"
        print("[OK] P5-9 查看最新提交")

        # ========== P5: 批改 + 通知 ==========
        sub_id = sub.json()["id"]
        r = client.post(f"/api/v1/submissions/{sub_id}/grade", json={"score": 90, "feedback": "实现完整"}, headers=_auth(admin_t))
        assert r.status_code == 200 and r.json()["score"] == 90, r.text
        # 学生收到评分通知
        r = client.get("/api/v1/notifications", headers=_auth(s1_t))
        assert r.json()["total"] == 2, f"应收到2条通知: {r.text}"
        print("[OK] P5-10 教师批改 + 学生收到评分通知")

        # ========== P5: 统计 ==========
        r = client.get(f"/api/v1/assignments/{aid}/stats", headers=_auth(admin_t))
        stats = r.json()
        assert stats["total_students"] == 2 and stats["submitted_count"] == 1
        assert len(stats["not_submitted"]) == 1  # 李四未交
        print(f"[OK] P5-11 作业统计: 提交{stats['submitted_count']}/总数{stats['total_students']}，未交{len(stats['not_submitted'])}人")

        # ========== P5: 版本历史 ==========
        r = client.get(f"/api/v1/submissions/{sub_id}/versions", headers=_auth(s1_t))
        assert len(r.json()) == 2, r.text
        print("[OK] P5-12 提交版本历史(2条)")

        # ========== P5: 课表 + NL 查询 ==========
        r = client.get("/api/v1/schedule/today", headers=_auth(s1_t))
        assert r.status_code == 200
        print(f"[OK] P5-13 今日课表: {len(r.json())}门课")

        r = client.post("/api/v1/courses/query-nl", json={"text": "数据结构什么时候"}, headers=_auth(s1_t))
        nl = r.json()
        assert nl["intent"] == "course_search" and nl["count"] > 0, nl
        print(f"[OK] P5-14 NL课程查询「数据结构什么时候」: 命中{nl['count']}条安排")

        r = client.post("/api/v1/courses/query-nl", json={"text": "明天有什么课"}, headers=_auth(s1_t))
        assert r.json()["intent"] == "day_schedule"
        print("[OK] P5-15 NL课程查询「明天有什么课」-> day_schedule")

        # ========== P6: Skills ==========
        r = client.get("/api/v1/admin/skills", headers=_auth(admin_t))
        assert r.json()["total"] == 6, r.text
        print(f"[OK] P6-1 Skill 列表: {r.json()['total']}个")

        # 调用 skill（通过对话 @总结）
        r = client.post("/api/v1/chat/sessions", json={"title": "skill测试"}, headers=_auth(s1_t))
        sid = r.json()["id"]
        r = client.post(f"/api/v1/chat/sessions/{sid}/messages/simple",
                        json={"content": "@总结 这是一段需要总结的文本，包含多个要点。", "rag_scope": "none"},
                        headers=_auth(s1_t))
        assert r.status_code == 200 and r.json()["ai_message"]["skill"] == "summary", r.text
        print("[OK] P6-2 @总结 Skill 调用成功并记录")

        # skill 调用记录
        r = client.get("/api/v1/admin/skills/calls?skill_name=summary", headers=_auth(admin_t))
        assert r.json()["total"] >= 1, r.text
        print(f"[OK] P6-3 Skill 调用记录: {r.json()['total']}条")

        # 禁用 skill 后无法触发
        skill_id = [s for s in client.get("/api/v1/admin/skills", headers=_auth(admin_t)).json()["items"] if s["name"] == "polish"][0]["id"]
        client.put(f"/api/v1/admin/skills/{skill_id}", json={"is_enabled": False}, headers=_auth(admin_t))
        r = client.post(f"/api/v1/chat/sessions/{sid}/messages/simple",
                        json={"content": "@润色 测试文本", "rag_scope": "none"}, headers=_auth(s1_t))
        assert r.json()["ai_message"]["skill"] is None, "禁用的 skill 不应触发"
        print("[OK] P6-4 禁用 Skill 后触发词失效")
        # 重新启用
        client.put(f"/api/v1/admin/skills/{skill_id}", json={"is_enabled": True}, headers=_auth(admin_t))

        # ========== P6: MCP 工具 ==========
        mcp_h = {"X-Service-Token": "test-mcp-token"}
        # 无 token 被拒
        r = client.post("/api/v1/mcp/render-mindmap", json={"content": "# 标题"})
        assert r.status_code == 401, "MCP 无 token 应拒绝"
        print("[OK] P6-5 MCP 服务令牌鉴权")

        # parse-file
        r = client.post("/api/v1/mcp/parse-file", files={"file": ("t.txt", io.BytesIO("MCP测试内容".encode()), "text/plain")}, headers=mcp_h)
        assert r.status_code == 200 and r.json()["chunk_count"] >= 1, r.text
        print("[OK] P6-6 MCP parse-file")

        # search-knowledge（先上传一个文件到知识库）
        client.post("/api/v1/knowledge/upload", files={"file": ("note.txt", io.BytesIO("龙马视界项目使用FastAPI框架".encode()), "text/plain")}, headers=_auth(s1_t))
        r = client.post("/api/v1/mcp/search-knowledge", json={"query": "FastAPI", "scope": "all", "user_id": s1.id}, headers=mcp_h)
        assert r.status_code == 200 and r.json()["count"] >= 1, r.text
        print(f"[OK] P6-7 MCP search-knowledge: 命中{r.json()['count']}条")

        # render-mindmap
        r = client.post("/api/v1/mcp/render-mindmap", json={"content": "# 主题\n## 子项A\n### 细节\n## 子项B"}, headers=mcp_h)
        tree = r.json()["tree"]
        assert tree["title"] == "思维导图" and len(tree["children"]) == 1
        print("[OK] P6-8 MCP render-mindmap 树结构生成")

        # fetch-page SSRF 防护
        r = client.post("/api/v1/mcp/fetch-page", json={"url": "http://127.0.0.1:9999/"}, headers=mcp_h)
        assert r.status_code in (400, 502), f"SSRF 内网应被拦截: {r.status_code}"
        print("[OK] P6-9 MCP fetch-page SSRF 防护(拦截内网)")

        r = client.post("/api/v1/mcp/fetch-page", json={"url": "ftp://example.com"}, headers=mcp_h)
        assert r.status_code == 400, "非 http 协议应拒绝"
        print("[OK] P6-10 MCP fetch-page 拒绝非 http 协议")

        # ========== P7: 审计 ==========
        r = client.get("/api/v1/admin/audit?page_size=5", headers=_auth(admin_t))
        assert r.status_code == 200 and r.json()["total"] > 0, r.text
        # 审计应记录了写操作（create/update 等）
        actions = {item["action"] for item in r.json()["items"]}
        assert "create" in actions or "update" in actions, f"审计应含写操作: {actions}"
        print(f"[OK] P7-1 审计日志: 共{r.json()['total']}条，含操作 {actions}")

        # 审计不应记录密码（detail 为空）
        for item in r.json()["items"]:
            assert item["detail"] is None, "审计 detail 不应含敏感信息"
        print("[OK] P7-2 审计日志不含敏感请求体")

        # ========== P7: 统计 ==========
        r = client.get("/api/v1/admin/stats", headers=_auth(admin_t))
        s = r.json()
        assert s["users"]["total"] == 3 and s["assignments"]["assignments"] == 1, s
        assert s["skills"]["skills"] == 6, s
        print(f"[OK] P7-3 系统统计: 用户{s['users']['total']} 作业{s['assignments']['assignments']} Skills调用{s['skills']['calls']}")

        # ========== P7: 配置 ==========
        r = client.get("/api/v1/admin/config", headers=_auth(admin_t))
        assert r.json()["class_name"] == "大数据管理与应用25级"
        r = client.put("/api/v1/admin/config", json={"class_name": "测试班级"}, headers=_auth(admin_t))
        assert r.json()["class_name"] == "测试班级"
        print("[OK] P7-4 系统配置读写")

        # ========== P7: 存储用量 ==========
        r = client.get("/api/v1/admin/storage", headers=_auth(admin_t))
        assert r.status_code == 200 and r.json()["personal_total_bytes"] > 0, r.text
        print(f"[OK] P7-5 存储用量: 个人{r.json()['personal_total_bytes']}字节")

        print("\n========== P5-P7 全流程测试通过 ==========")


if __name__ == "__main__":
    test_p5_p7_flow()
