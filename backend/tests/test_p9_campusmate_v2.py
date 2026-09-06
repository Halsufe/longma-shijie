"""
P9 CampusMate V2.0 集成测试：角色与用户信息 / 成果档案 / 资源社区 / 教师方向 / 交流申请 / 学习计划 / 管理员审核
"""
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
    cfg.settings.ENV = "test"
    cfg.settings.API_RATE_LIMIT = 100000

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
        student_no="admin", name="系统管理员",
        password_hash=hash_password("Admin@123"),
        role="admin", status="active",
    )
    student = User(
        student_no="2025001", name="张三",
        password_hash=hash_password("User@123"),
        role="student", status="active",
        profile_json='{"major":"计算机","research":["AI","机器学习"],"skills":["Python","Java"]}',
    )
    teacher = User(
        student_no="T001", name="李教授",
        password_hash=hash_password("Teacher@123"),
        role="teacher", status="active",
        profile_json='{"field":"人工智能","research_directions":["深度学习","NLP"]}',
    )
    student2 = User(
        student_no="2025002", name="李四",
        password_hash=hash_password("User@123"),
        role="student", status="active",
    )
    alumni = User(
        student_no="A001", name="王校友",
        password_hash=hash_password("User@123"),
        role="alumni", status="active",
        graduation_year=2024,
    )
    db.add_all([admin, student, teacher, student2, alumni])
    db.commit()
    for u in [admin, student, teacher, student2, alumni]:
        db.refresh(u)
    return admin, student, teacher, student2, alumni


def _login(client, student_no, password):
    r = client.post("/api/v1/auth/login", json={"student_no": student_no, "password": password})
    assert r.status_code == 200, f"login failed: {r.text}"
    return r.json()


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_p9_campusmate_v2():
    with tempfile.TemporaryDirectory() as tmp:
        app, db_mod = _setup_app(tmp)
        client = TestClient(app)
        db = db_mod.SessionLocal()
        try:
            admin, student, teacher, student2, alumni = _seed_users(db)
        finally:
            db.close()

        # === P9-1: 角色与用户信息 ===
        print("\n=== P9-1: 角色与用户信息 ===")

        s_login = _login(client, "2025001", "User@123")
        s_token = s_login["access_token"]
        s_headers = _auth(s_token)

        r = client.get("/api/v1/users/me", headers=s_headers)
        assert r.status_code == 200
        me = r.json()
        assert me["role"] == "student"
        assert me["profile"]["major"] == "计算机"
        print("  [OK] 学生登录 + 个人信息（含 profile）")

        r = client.put("/api/v1/users/me", headers=s_headers, json={
            "profile": {"major": "人工智能", "research": ["AI", "深度学习"], "skills": ["Python", "PyTorch"]}
        })
        assert r.status_code == 200
        assert r.json()["profile"]["major"] == "人工智能"
        print("  [OK] 更新 profile")

        a_login = _login(client, "A001", "User@123")
        a_token = a_login["access_token"]
        a_headers = _auth(a_token)
        r = client.get("/api/v1/users/me", headers=a_headers)
        assert r.status_code == 200
        assert r.json()["role"] == "alumni"
        assert r.json()["graduation_year"] == 2024
        print("  [OK] 校友角色 + 毕业年份")

        # === P9-2: 成果档案 ===
        print("\n=== P9-2: 成果档案 ===")

        r = client.post("/api/v1/achievements", headers=s_headers, json={
            "category": "award",
            "title": "全国大学生数学建模竞赛一等奖",
            "description": "2024年全国赛一等奖",
            "achievement_date": "2024-11",
            "level": "国家级",
            "is_public": True,
        })
        assert r.status_code == 200
        ach_id = r.json()["id"]
        assert r.json()["category"] == "award"
        assert r.json()["status"] == "pending"
        print("  [OK] 创建成果")

        r = client.get("/api/v1/achievements", headers=s_headers)
        assert r.status_code == 200
        assert r.json()["total"] >= 1
        print("  [OK] 列出我的成果")

        # 公开列表：pending 状态不可见，需管理员批准
        # 先用管理员登录批准，再验证
        adm_login = _login(client, "admin", "Admin@123")
        adm_token = adm_login["access_token"]
        adm_headers = _auth(adm_token)

        r = client.put(f"/api/v1/achievements/admin/{ach_id}/approve", headers=adm_headers)
        assert r.status_code == 200
        assert r.json()["status"] == "approved"
        print("  [OK] 管理员批准成果")

        r = client.get("/api/v1/achievements/public/list", headers=s_headers)
        assert r.status_code == 200
        assert r.json()["total"] >= 1
        print("  [OK] 公开列表（批准后可见）")

        s2_login = _login(client, "2025002", "User@123")
        s2_token = s2_login["access_token"]
        s2_headers = _auth(s2_token)
        r = client.get("/api/v1/achievements", headers=s2_headers)
        assert r.status_code == 200
        assert r.json()["total"] == 0
        print("  [OK] 成果权限隔离")

        r = client.put(f"/api/v1/achievements/{ach_id}", headers=s_headers, json={
            "description": "更新后的描述"
        })
        assert r.status_code == 200
        assert r.json()["description"] == "更新后的描述"
        print("  [OK] 更新成果")

        r = client.delete(f"/api/v1/achievements/{ach_id}", headers=s_headers)
        assert r.status_code == 200
        assert r.json()["success"] == True
        print("  [OK] 删除成果")

        # === P9-3: 资源社区 ===
        print("\n=== P9-3: 资源社区 ===")

        t_login = _login(client, "T001", "Teacher@123")
        t_token = t_login["access_token"]
        t_headers = _auth(t_token)

        r = client.post("/api/v1/resources", headers=t_headers, json={
            "type": "material",
            "title": "深度学习入门资料",
            "content": "包含课件、代码和数据集",
            "tags": ["AI", "深度学习", "入门"],
        })
        assert r.status_code == 200
        res_id = r.json()["id"]
        print("  [OK] 教师发布资源")

        r = client.get("/api/v1/resources", headers=s_headers)
        assert r.status_code == 200
        assert r.json()["total"] >= 1
        print("  [OK] 资源列表")

        r = client.get(f"/api/v1/resources/{res_id}", headers=s_headers)
        assert r.status_code == 200
        assert r.json()["view_count"] >= 1
        print("  [OK] 资源详情 + 浏览量")

        r = client.post(f"/api/v1/resources/{res_id}/favorite", headers=s_headers)
        assert r.status_code == 200
        r = client.get("/api/v1/resources/favorites", headers=s_headers)
        assert r.status_code == 200
        assert r.json()["total"] >= 1
        print("  [OK] 收藏 + 列表收藏")

        r = client.post(f"/api/v1/resources/{res_id}/like", headers=s_headers)
        assert r.status_code == 200
        r = client.get(f"/api/v1/resources/{res_id}", headers=s_headers)
        assert r.json()["like_count"] >= 1
        print("  [OK] 点赞")

        # === P9-4: 教师方向 ===
        print("\n=== P9-4: 教师方向 ===")

        r = client.post("/api/v1/teachers/directions", headers=t_headers, json={
            "title": "人工智能与深度学习",
            "description": "招收对 AI 感兴趣的学生进行科研指导",
            "tags": ["AI", "深度学习", "NLP"],
        })
        assert r.status_code == 200
        dir_id = r.json()["id"]
        print("  [OK] 教师创建方向")

        r = client.get("/api/v1/teachers/directions/mine", headers=t_headers)
        assert r.status_code == 200
        assert r.json()["total"] >= 1
        print("  [OK] 教师列出方向")

        r = client.get("/api/v1/teachers/match", headers=s_headers, params={"q": "人工智能"})
        assert r.status_code == 200
        assert r.json()["total"] >= 1
        print("  [OK] 学生搜索匹配教师")

        # === P9-5: 交流申请 ===
        print("\n=== P9-5: 交流申请 ===")

        r = client.post("/api/v1/applications", headers=s_headers, json={
            "teacher_id": teacher.id,
            "direction_id": dir_id,
            "title": "想请教关于深度学习的问题",
            "message": "老师您好，我对深度学习很感兴趣，希望能得到指导。",
        })
        assert r.status_code == 200
        app_id = r.json()["id"]
        assert r.json()["status"] == "pending"
        print("  [OK] 学生提交交流申请")

        r = client.get("/api/v1/applications/mine/sent", headers=s_headers)
        assert r.status_code == 200
        assert r.json()["total"] >= 1
        print("  [OK] 学生查看已提交申请")

        r = client.get("/api/v1/applications/mine/received", headers=t_headers)
        assert r.status_code == 200
        assert r.json()["total"] >= 1
        print("  [OK] 教师查看收到申请")

        r = client.put(f"/api/v1/applications/{app_id}/accept", headers=t_headers)
        assert r.status_code == 200
        assert r.json()["status"] == "accepted"
        print("  [OK] 教师接受申请")

        # === P9-6: 学习计划 ===
        print("\n=== P9-6: 学习计划 ===")

        r = client.post("/api/v1/applications/plans", headers=s_headers, json={
            "title": "深度学习学习计划",
            "description": "6周入门深度学习",
            "items": [
                {"week": 1, "task": "学习线性代数和微积分基础"},
                {"week": 2, "task": "学习 Python 和 PyTorch"},
                {"week": 3, "task": "实现简单的神经网络"},
            ],
            "reminder_at": "2026-09-01T09:00:00Z",
        })
        assert r.status_code == 200
        plan_id = r.json()["id"]
        print("  [OK] 创建学习计划")

        r = client.get("/api/v1/applications/plans/mine", headers=s_headers)
        assert r.status_code == 200
        assert r.json()["total"] >= 1
        print("  [OK] 列出学习计划")

        r = client.put(f"/api/v1/applications/plans/{plan_id}", headers=s_headers, json={
            "is_completed": True
        })
        assert r.status_code == 200
        assert r.json()["is_completed"] == True
        print("  [OK] 更新计划（标记完成）")

        r = client.get("/api/v1/applications/plans/mine", headers=s_headers, params={"is_completed": "true"})
        assert r.status_code == 200
        assert r.json()["total"] >= 1
        print("  [OK] 按状态筛选计划")

        r = client.delete(f"/api/v1/applications/plans/{plan_id}", headers=s_headers)
        assert r.status_code == 200
        print("  [OK] 删除计划")

        # === P9-7: 管理员审核 ===
        print("\n=== P9-7: 管理员审核 ===")

        r = client.get("/api/v1/achievements/admin/all", headers=adm_headers)
        assert r.status_code == 200
        print("  [OK] 管理员列出全部成果")

        s_login2 = _login(client, "2025001", "User@123")
        s_token2 = s_login2["access_token"]
        s_headers2 = _auth(s_token2)

        r = client.post("/api/v1/achievements", headers=s_headers2, json={
            "category": "paper",
            "title": "基于深度学习的图像识别研究",
            "is_public": True,
        })
        assert r.status_code == 200
        new_ach_id = r.json()["id"]

        r = client.put(f"/api/v1/achievements/admin/{new_ach_id}/approve", headers=adm_headers)
        assert r.status_code == 200
        assert r.json()["status"] == "approved"
        print("  [OK] 管理员批准成果")

        r = client.get("/api/v1/achievements/public/list", headers=adm_headers)
        assert r.status_code == 200
        assert any(item["id"] == new_ach_id for item in r.json()["items"])
        print("  [OK] 批准后成果可见于公开列表")

        print("\n=== P9 CampusMate V2.0 集成测试完成 ===")


if __name__ == "__main__":
    test_p9_campusmate_v2()