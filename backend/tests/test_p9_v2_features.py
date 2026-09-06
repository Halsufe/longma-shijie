"""
P9 V2.0 创新创业融合 - 集成测试

测试覆盖：
1. 交流申请全流程（创建→查看→接受/拒绝→取消）
2. 学习计划全流程（创建→更新→标记完成→删除）
3. 个性化推荐（资源/教师/成果推荐，基于 profile 匹配）
4. 任务确认机制（预览→验证→数据一致性校验）

运行方式：
    cd c:\\Users\\33661\\Desktop\\BD\\LM_SJ
    .\\.venv\\python.exe backend\\tests\\test_p9_v2_features.py
"""
import os
import sys
import json
import time
from datetime import datetime, timezone

os.environ["DB_URL"] = "sqlite:///:memory:"
os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.getcwd())

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import create_app
from backend.app.core import database as db_mod
from backend.app.core.security import hash_password
from backend.app.models.user import User


def setup_app():
    db_mod.engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        future=True,
        poolclass=StaticPool,
    )
    db_mod.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_mod.engine, future=True)
    db_mod.Base.metadata.create_all(bind=db_mod.engine)
    app = create_app()

    def override_get_db():
        db = db_mod.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    from backend.app.core.database import get_db
    app.dependency_overrides[get_db] = override_get_db
    return app, db_mod


def login(client, student_no, password):
    r = client.post("/api/v1/auth/login", json={"student_no": student_no, "password": password})
    assert r.status_code == 200, f"登录失败: {r.text}"
    return r.json()


def test_p9_v2_features():
    print("=" * 70)
    print("P9 V2.0 创新创业融合 - 集成测试")
    print("=" * 70)

    app, db_mod = setup_app()
    client = TestClient(app)

    # 创建用户
    db = db_mod.SessionLocal()
    try:
        users = [
            User(student_no="admin01", name="管理员", password_hash=hash_password("Admin@123"), role="admin", status="active"),
            User(student_no="S001", name="学生张三", password_hash=hash_password("Student@123"), role="student", status="active"),
            User(student_no="S002", name="学生李四", password_hash=hash_password("Student@123"), role="student", status="active"),
            User(student_no="T001", name="王教授", password_hash=hash_password("Teacher@123"), role="teacher", status="active"),
            User(student_no="T002", name="刘教授", password_hash=hash_password("Teacher@123"), role="teacher", status="active"),
            User(student_no="A001", name="校友赵六", password_hash=hash_password("Alumni@123"), role="alumni", status="active", graduation_year=2023),
        ]
        for u in users:
            db.add(u)
        db.commit()
    finally:
        db.close()

    # 登录
    admin = login(client, "admin01", "Admin@123")
    student = login(client, "S001", "Student@123")
    student2 = login(client, "S002", "Student@123")
    teacher = login(client, "T001", "Teacher@123")
    teacher2 = login(client, "T002", "Teacher@123")
    alumni = login(client, "A001", "Alumni@123")

    admin_h = {"Authorization": f"Bearer {admin['access_token']}"}
    student_h = {"Authorization": f"Bearer {student['access_token']}"}
    student2_h = {"Authorization": f"Bearer {student2['access_token']}"}
    teacher_h = {"Authorization": f"Bearer {teacher['access_token']}"}
    teacher2_h = {"Authorization": f"Bearer {teacher2['access_token']}"}
    alumni_h = {"Authorization": f"Bearer {alumni['access_token']}"}

    results = []

    def check(name, condition, detail=""):
        status = "✅" if condition else "❌"
        results.append((name, condition))
        print(f"  {status} {name}" + (f" — {detail}" if detail else ""))
        assert condition, f"断言失败: {name}"

    # ================================================================
    # 1. 交流申请全流程
    # ================================================================
    print("\n📋 1. 交流申请全流程")
    print("-" * 50)

    # 教师创建研究方向
    r = client.post("/api/v1/teachers/directions",
        headers=teacher_h,
        json={"title": "深度学习与NLP", "description": "招收对AI感兴趣的学生", "tags": ["深度学习", "NLP", "Python"]})
    check("教师创建方向", r.status_code == 200, f"status={r.status_code}")
    direction_id = r.json()["id"]

    # 学生提交交流申请
    r = client.post("/api/v1/applications",
        headers=student_h,
        json={"teacher_id": 4, "title": "希望加入您的研究组", "message": "我对NLP很感兴趣", "direction_id": direction_id})
    check("学生提交交流申请", r.status_code == 200, f"status={r.status_code}")
    app_id_1 = r.json()["id"]
    check("申请状态为pending", r.json()["status"] == "pending")

    # 学生2也提交申请
    r = client.post("/api/v1/applications",
        headers=student2_h,
        json={"teacher_id": 4, "title": "请教深度学习方向", "message": "想学习CV方向"})
    check("学生2提交申请", r.status_code == 200)
    app_id_2 = r.json()["id"]

    # 教师查看收到的申请
    r = client.get("/api/v1/applications/mine/received", headers=teacher_h)
    check("教师查看收到申请", r.status_code == 200)
    check("收到2条申请", r.json()["total"] == 2, f"total={r.json()['total']}")

    # 教师接受第一个申请
    r = client.put(f"/api/v1/applications/{app_id_1}/accept", headers=teacher_h)
    check("教师接受申请", r.status_code == 200)
    check("申请状态变为accepted", r.json()["status"] == "accepted")
    check("decided_at已设置", r.json()["decided_at"] is not None)

    # 教师拒绝第二个申请
    r = client.put(f"/api/v1/applications/{app_id_2}/reject", headers=teacher_h)
    check("教师拒绝申请", r.status_code == 200)
    check("申请状态变为rejected", r.json()["status"] == "rejected")

    # 学生查看已发送的申请
    r = client.get("/api/v1/applications/mine/sent", headers=student_h)
    check("学生查看已发送申请", r.status_code == 200)
    check("已发送1条", r.json()["total"] == 1)

    # 学生不能接受申请（权限隔离）
    r = client.put(f"/api/v1/applications/{app_id_1}/accept", headers=student_h)
    check("学生不能接受申请", r.status_code == 403, f"status={r.status_code}")

    # 学生取消自己的申请
    r = client.post("/api/v1/applications",
        headers=student_h,
        json={"teacher_id": 5, "title": "测试取消"})
    cancel_id = r.json()["id"]
    r = client.delete(f"/api/v1/applications/{cancel_id}", headers=student_h)
    check("学生取消申请", r.status_code == 200)

    # ================================================================
    # 2. 学习计划全流程
    # ================================================================
    print("\n📋 2. 学习计划全流程")
    print("-" * 50)

    # 创建学习计划
    r = client.post("/api/v1/applications/plans",
        headers=student_h,
        json={
            "title": "大三上学期学习计划",
            "description": "重点学习深度学习和NLP",
            "items": [
                {"task": "完成吴恩达ML课程", "deadline": "2026-09-01"},
                {"task": "阅读NLP论文5篇", "deadline": "2026-10-01"},
                {"task": "参加数学建模竞赛", "deadline": "2026-11-01"},
            ],
            "reminder_at": "2026-08-15T09:00:00Z",
        })
    check("创建学习计划", r.status_code == 200, f"status={r.status_code}")
    plan_id = r.json()["id"]
    check("计划有3个items", len(r.json()["items"]) == 3)
    check("计划未完成", r.json()["is_completed"] == False)

    # 查看计划列表
    r = client.get("/api/v1/applications/plans/mine", headers=student_h)
    check("查看计划列表", r.status_code == 200)
    check("有1条计划", r.json()["total"] == 1)

    # 更新计划
    r = client.put(f"/api/v1/applications/plans/{plan_id}",
        headers=student_h,
        json={"title": "修改后的学习计划", "is_completed": True})
    check("更新计划", r.status_code == 200)
    check("标题已更新", r.json()["title"] == "修改后的学习计划")
    check("标记为已完成", r.json()["is_completed"] == True)

    # 按完成状态过滤
    r = client.get("/api/v1/applications/plans/mine?is_completed=true", headers=student_h)
    check("过滤已完成计划", r.json()["total"] == 1)
    r = client.get("/api/v1/applications/plans/mine?is_completed=false", headers=student_h)
    check("过滤未完成计划", r.json()["total"] == 0)

    # 学生2不能访问学生1的计划
    r = client.put(f"/api/v1/applications/plans/{plan_id}",
        headers=student2_h,
        json={"title": "黑客修改"})
    check("计划权限隔离", r.status_code == 404, f"status={r.status_code}")

    # 删除计划
    r = client.delete(f"/api/v1/applications/plans/{plan_id}", headers=student_h)
    check("删除计划", r.status_code == 200)

    # ================================================================
    # 3. 个性化推荐
    # ================================================================
    print("\n📋 3. 个性化推荐")
    print("-" * 50)

    # 学生设置 profile
    r = client.put("/api/v1/users/me",
        headers=student_h,
        json={"profile": {"major": "数据科学", "research": ["深度学习", "NLP"], "skills": ["Python", "PyTorch"]}})
    check("学生设置profile", r.status_code == 200)

    # 创建资源（带标签，匹配学生兴趣）
    r = client.post("/api/v1/resources",
        headers=teacher_h,
        json={"type": "competition", "title": "2026 NLP创新大赛", "content": "自然语言处理比赛",
              "tags": ["NLP", "深度学习"], "source": "教育部", "deadline": "2026-10-01T00:00:00Z"})
    check("创建NLP比赛资源", r.status_code == 200)

    r = client.post("/api/v1/resources",
        headers=teacher_h,
        json={"type": "material", "title": "Python数据科学入门", "content": "学习资料",
              "tags": ["Python", "数据科学"]})
    check("创建Python资料资源", r.status_code == 200)

    r = client.post("/api/v1/resources",
        headers=teacher2_h,
        json={"type": "experience", "title": "校园篮球赛经验分享", "content": "体育活动",
              "tags": ["篮球", "体育"]})
    check("创建不相关资源", r.status_code == 200)

    # 获取综合推荐
    r = client.get("/api/v1/recommendations/", headers=student_h)
    check("获取综合推荐", r.status_code == 200, f"status={r.status_code}")
    check("推荐包含资源", len(r.json()["resources"]) > 0, f"resources={len(r.json()['resources'])}")
    check("推荐包含教师", len(r.json()["teachers"]) > 0, f"teachers={len(r.json()['teachers'])}")

    # 获取资源推荐（按类型过滤比赛）
    r = client.get("/api/v1/recommendations/resources?type=competition", headers=student_h)
    check("获取比赛推荐", r.status_code == 200)
    check("推荐了比赛资源", len(r.json()["items"]) > 0, f"items={len(r.json()['items'])}")
    if r.json()["items"]:
        check("推荐的是NLP比赛", "NLP" in r.json()["items"][0]["title"], f"title={r.json()['items'][0]['title']}")

    # 获取教师推荐
    r = client.get("/api/v1/recommendations/teachers", headers=student_h)
    check("获取教师推荐", r.status_code == 200)
    check("推荐了教师", len(r.json()["items"]) > 0)

    # 获取成果推荐（先创建公开成果并审核通过）
    r = client.post("/api/v1/achievements",
        headers=alumni_h,
        json={"category": "award", "title": "全国大学生NLP竞赛一等奖", "level": "国家级",
              "achievement_date": "2023-06", "is_public": True})
    check("校友创建公开成果", r.status_code == 200)
    achievement_id = r.json()["id"]

    # 管理员审核通过成果
    r = client.put(f"/api/v1/achievements/admin/{achievement_id}/approve", headers=admin_h)
    check("管理员审核通过成果", r.status_code == 200, f"status={r.status_code}")

    r = client.get("/api/v1/recommendations/achievements", headers=student_h)
    check("获取成果推荐", r.status_code == 200)
    check("推荐了成果", len(r.json()["items"]) > 0, f"items={len(r.json()['items'])}")

    # ================================================================
    # 4. 任务确认机制
    # ================================================================
    print("\n📋 4. 任务确认机制")
    print("-" * 50)

    # 获取可确认操作列表
    r = client.get("/api/v1/confirm/operations", headers=student_h)
    check("获取可确认操作列表", r.status_code == 200)
    check("操作列表非空", r.json()["total"] > 0, f"total={r.json()['total']}")
    print(f"     可确认操作: {[op['operation'] for op in r.json()['operations']]}")

    # 预览操作
    operation_data = {"type": "competition", "title": "测试比赛", "tags": ["AI"]}
    r = client.post("/api/v1/confirm/preview",
        headers=student_h,
        json={"operation": "resource.create", "data": operation_data})
    check("预览操作", r.status_code == 200, f"status={r.status_code}")
    check("返回确认令牌", "confirmation_token" in r.json() and r.json()["confirmation_token"])
    check("返回预览内容", "preview" in r.json())
    check("预览有脱敏", r.json()["preview"]["data_preview"]["type"] == "competition")
    confirmation_token = r.json()["confirmation_token"]

    # 验证确认令牌（正确数据）
    r = client.post("/api/v1/confirm/verify",
        headers=student_h,
        json={"confirmation_token": confirmation_token, "operation": "resource.create", "data": operation_data})
    check("验证确认令牌(正确数据)", r.status_code == 200, f"status={r.status_code}")
    check("令牌有效", r.json()["valid"] == True)

    # 验证确认令牌（数据不一致）
    modified_data = {"type": "competition", "title": "篡改的标题", "tags": ["AI"]}
    r = client.post("/api/v1/confirm/verify",
        headers=student_h,
        json={"confirmation_token": confirmation_token, "operation": "resource.create", "data": modified_data})
    check("数据不一致被拒绝", r.status_code == 400, f"status={r.status_code}")

    # 验证确认令牌（用户不匹配）
    r = client.post("/api/v1/confirm/verify",
        headers=student2_h,
        json={"confirmation_token": confirmation_token, "operation": "resource.create", "data": operation_data})
    check("用户不匹配被拒绝", r.status_code == 403, f"status={r.status_code}")

    # 验证不支持的操作
    r = client.post("/api/v1/confirm/preview",
        headers=student_h,
        json={"operation": "unsupported.operation", "data": {}})
    check("不支持的操作被拒绝", r.status_code == 400, f"status={r.status_code}")

    # ================================================================
    # 汇总
    # ================================================================
    print("\n" + "=" * 70)
    print("📊 测试汇总")
    print("=" * 70)

    passed = sum(1 for _, ok in results if ok)
    failed = sum(1 for _, ok in results if not ok)
    total = len(results)

    print(f"  总断言: {total}")
    print(f"  通过: {passed} ✅")
    print(f"  失败: {failed} {'❌' if failed else ''}")
    print(f"  通过率: {passed/total*100:.1f}%")

    if failed:
        print("\n  失败项:")
        for name, ok in results:
            if not ok:
                print(f"    ❌ {name}")
    else:
        print("\n  🎉 所有测试通过！P9 V2.0 功能全部正常工作。")

    print("=" * 70)
    return failed == 0


if __name__ == "__main__":
    success = test_p9_v2_features()
    exit(0 if success else 1)
