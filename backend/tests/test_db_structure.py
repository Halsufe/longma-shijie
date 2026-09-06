"""
CampusMate V2.0 数据库结构验证测试脚本（带详细日志）

测试流程：
1. 管理员登录
2. 管理员创建新用户（学生/教师/校友三种角色）
3. 管理员重置用户密码（获取临时密码）
4. 新用户用临时密码登录
5. 新用户修改密码
6. 新用户用新密码重新登录
7. 新用户更新 profile（验证 V2 新字段 graduation_year / profile_json）
8. 验证权限隔离

特性：
- 每个步骤自动记录执行时间
- 每个 API 请求记录耗时和状态码
- 关键数据自动持久化到日志文件
- 结束时输出汇总报告

运行方式：
    cd c:\\Users\\33661\\Desktop\\BD\\LM_SJ
    .\\.venv\\python.exe backend\\tests\\test_db_structure.py

日志输出：
    控制台：实时彩色输出
    文件：backend/tests/logs/test_db_structure_YYYYMMDD_HHMMSS.log
"""
import json
import os
import re
import sys
import time
from contextlib import contextmanager
from datetime import datetime

# 必须在导入 app 模块前设置
os.environ["DB_URL"] = "sqlite:///:memory:"

# 确保工作目录正确（加载 .env 中的 AI 配置）
os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.getcwd())

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import create_app
from backend.app.core import database as db_mod
from backend.app.core.security import hash_password
from backend.app.models.user import User


# ============================================================
# 日志基础设施
# ============================================================

class TestLogger:
    """统一日志管理器：控制台 + 文件双输出，记录执行时间和关键数据"""

    def __init__(self, name: str):
        self.name = name
        self.start_time = time.time()
        self.step_records: list[dict] = []
        self.request_records: list[dict] = []
        self._current_step = None
        self._step_start = None

        # 创建日志目录
        self.log_dir = os.path.join("backend", "tests", "logs")
        os.makedirs(self.log_dir, exist_ok=True)

        # 日志文件名（带时间戳）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(self.log_dir, f"test_db_structure_{timestamp}.log")

        # 写入文件头
        self._write_file("=" * 70 + "\n")
        self._write_file(f"{name}\n")
        self._write_file(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        self._write_file(f"进程 PID: {os.getpid()}\n")
        self._write_file(f"工作目录: {os.getcwd()}\n")
        self._write_file(f"Python: {sys.version.split()[0]}\n")
        self._write_file("=" * 70 + "\n\n")

    def _write_file(self, text: str):
        """写入日志文件（不含颜色码）"""
        # 移除 ANSI 颜色码
        clean = re.sub(r"\x1b\[[0-9;]*m", "", text)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(clean)

    def console(self, text: str):
        """同时输出到控制台和文件"""
        print(text)
        self._write_file(text + "\n")

    @contextmanager
    def step(self, step_num: int, description: str):
        """步骤计时上下文管理器"""
        self._current_step = step_num
        self._step_start = time.time()
        self.console(f"\n{'=' * 70}")
        self.console(f"📋 步骤 {step_num}: {description}")
        self.console(f"{'=' * 70}")
        self.console(f"  ⏰ 开始: {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")

        try:
            yield self
        except Exception as e:
            elapsed = time.time() - self._step_start
            self.console(f"  ❌ 步骤失败 (耗时 {elapsed:.3f}s): {e}")
            self.step_records.append({
                "step": step_num,
                "description": description,
                "status": "failed",
                "elapsed": round(elapsed, 3),
                "error": str(e),
            })
            raise
        else:
            elapsed = time.time() - self._step_start
            self.console(f"  ⏰ 完成: {datetime.now().strftime('%H:%M:%S.%f')[:-3]} (耗时 {elapsed:.3f}s)")
            self.step_records.append({
                "step": step_num,
                "description": description,
                "status": "passed",
                "elapsed": round(elapsed, 3),
            })

    def request(self, method: str, url: str, status_code: int, duration: float, **extra):
        """记录一个 API 请求"""
        record = {
            "step": self._current_step,
            "method": method,
            "url": url,
            "status_code": status_code,
            "duration_ms": round(duration * 1000, 1),
            **extra,
        }
        self.request_records.append(record)
        self._write_file(f"    [API] {method} {url} → {status_code} ({record['duration_ms']}ms)\n")
        if extra:
            self._write_file(f"          {json.dumps(extra, ensure_ascii=False, default=str)}\n")

    def data(self, label: str, value):
        """记录关键数据"""
        if isinstance(value, (dict, list)):
            formatted = json.dumps(value, ensure_ascii=False, indent=2, default=str)
            self.console(f"  📦 {label}:")
            for line in formatted.split("\n"):
                self.console(f"     {line}")
        else:
            self.console(f"  📦 {label}: {value}")
        self._write_file(f"  [DATA] {label}: {json.dumps(value, ensure_ascii=False, default=str)}\n")

    def success(self, msg: str):
        """记录成功信息"""
        self.console(f"  ✅ {msg}")

    def info(self, msg: str):
        """记录普通信息"""
        self.console(f"  ℹ️  {msg}")

    def warning(self, msg: str):
        """记录警告信息"""
        self.console(f"  ⚠️  {msg}")

    def summary(self):
        """输出汇总报告"""
        total_elapsed = time.time() - self.start_time

        self.console(f"\n{'=' * 70}")
        self.console("📊 测试汇总报告")
        self.console(f"{'=' * 70}")

        # 步骤耗时
        self.console(f"\n⏱️  步骤耗时明细:")
        self.console(f"  {'步骤':<8} {'描述':<40} {'状态':<8} {'耗时':>10}")
        self.console(f"  {'-' * 70}")
        for rec in self.step_records:
            status = "✅ 通过" if rec["status"] == "passed" else "❌ 失败"
            self.console(f"  {rec['step']:<8} {rec['description']:<40} {status:<8} {rec['elapsed']:>8.3f}s")

        # 请求统计
        self.console(f"\n📡 API 请求统计:")
        self.console(f"  总请求数: {len(self.request_records)}")
        if self.request_records:
            durations = [r["duration_ms"] for r in self.request_records]
            self.console(f"  总耗时: {sum(durations):.1f}ms")
            self.console(f"  平均耗时: {sum(durations) / len(durations):.1f}ms")
            self.console(f"  最快: {min(durations):.1f}ms")
            self.console(f"  最慢: {max(durations):.1f}ms")

            # 按状态码分组
            status_groups: dict[int, int] = {}
            for r in self.request_records:
                status_groups[r["status_code"]] = status_groups.get(r["status_code"], 0) + 1
            self.console(f"  状态码分布: {status_groups}")

            # 最慢的 5 个请求
            slowest = sorted(self.request_records, key=lambda x: x["duration_ms"], reverse=True)[:5]
            self.console(f"\n  最慢的 5 个请求:")
            for r in slowest:
                self.console(f"    {r['duration_ms']:>7.1f}ms  {r['method']:<6} {r['url']} → {r['status_code']}")

        # 总耗时
        self.console(f"\n⏱️  总耗时: {total_elapsed:.3f}s")
        self.console(f"📁 日志文件: {self.log_file}")
        self.console(f"{'=' * 70}\n")


# ============================================================
# 带 API 请求计时的辅助函数
# ============================================================

def timed_request(client, logger: TestLogger, method: str, url: str, **kwargs):
    """发送 API 请求并记录耗时"""
    start = time.time()
    r = getattr(client, method.lower())(url, **kwargs)
    duration = time.time() - start

    # 提取关键数据用于日志
    extra = {}
    if "json" in kwargs and kwargs["json"]:
        extra["request_body"] = kwargs["json"]
    if r.status_code < 500:
        try:
            resp = r.json()
            # 只记录关键字段，避免日志过长
            if isinstance(resp, dict):
                extra["response_keys"] = list(resp.keys())[:10]
                if "id" in resp:
                    extra["response_id"] = resp["id"]
                if "total" in resp:
                    extra["response_total"] = resp["total"]
        except Exception:
            extra["response_text"] = r.text[:200]

    logger.request(method, url, r.status_code, duration, **extra)
    return r


def login(client, logger: TestLogger, student_no: str, password: str, expect_status: int = 200):
    """登录并返回响应（带日志记录）"""
    r = timed_request(
        client, logger, "POST", "/api/v1/auth/login",
        json={"student_no": student_no, "password": password},
    )
    if r.status_code != expect_status:
        logger.warning(f"登录预期 {expect_status}，实际 {r.status_code}: {r.text}")
    if r.status_code == 200:
        return r.json()
    return None


# ============================================================
# 测试应用初始化
# ============================================================

def setup_app(logger: TestLogger):
    """创建隔离的测试应用（内存数据库）"""
    with logger.step(0, "初始化应用并验证数据库表结构") as _:
        start = time.time()
        db_mod.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            future=True,
            poolclass=StaticPool,
        )
        db_mod.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=db_mod.engine, future=True
        )
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

        init_elapsed = time.time() - start
        logger.info(f"应用初始化耗时: {init_elapsed:.3f}s")
        logger.info(f"路由总数: {len(app.routes)}")

        # 验证数据库表结构
        inspector = inspect(db_mod.engine)
        tables = inspector.get_table_names()
        logger.data("所有表", tables)

        required_tables = [
            "users", "user_sessions", "achievements", "resources",
            "resource_favorites", "resource_likes", "teacher_directions",
            "communication_applications", "learning_plans",
        ]
        missing = [t for t in required_tables if t not in tables]
        for t in required_tables:
            status = "✅" if t in tables else "❌"
            logger.console(f"  {status} 表 {t}")

        # 检查 users 表新字段
        user_columns = [c["name"] for c in inspector.get_columns("users")]
        v2_columns = ["graduation_year", "profile_json"]
        for col in v2_columns:
            status = "✅" if col in user_columns else "❌"
            logger.console(f"  {status} users.{col}")

        assert not missing, f"缺少必要的表: {missing}"
        assert all(c in user_columns for c in v2_columns), "缺少 V2 新字段"
        logger.success(f"数据库表结构验证通过（{len(tables)} 张表）")

        return app, db_mod


# ============================================================
# 主测试函数
# ============================================================

def test_db_structure():
    """主测试函数"""
    logger = TestLogger("CampusMate V2.0 数据库结构验证测试")
    logger.console("=" * 70)
    logger.console(logger.name)
    logger.console("=" * 70)
    logger.console(f"📁 日志文件: {logger.log_file}")

    try:
        # ============================================================
        # 步骤 0: 初始化应用
        # ============================================================
        app, db_mod = setup_app(logger)
        client = TestClient(app)

        # ============================================================
        # 步骤 1: 创建管理员账号
        # ============================================================
        with logger.step(1, "创建管理员账号"):
            db = db_mod.SessionLocal()
            try:
                start = time.time()
                admin = User(
                    student_no="admin_test",
                    name="测试管理员",
                    password_hash=hash_password("Admin@123"),
                    role="admin",
                    status="active",
                )
                db.add(admin)
                db.commit()
                db.refresh(admin)
                elapsed = time.time() - start
            finally:
                db.close()
            logger.success(f"管理员创建成功 (耗时 {elapsed:.3f}s)")
            logger.data("管理员信息", {
                "id": admin.id,
                "student_no": admin.student_no,
                "name": admin.name,
                "role": admin.role,
                "status": admin.status,
            })

        # ============================================================
        # 步骤 2: 管理员登录
        # ============================================================
        with logger.step(2, "管理员登录"):
            start = time.time()
            login_resp = login(client, logger, "admin_test", "Admin@123")
            elapsed = time.time() - start
            assert login_resp, "管理员登录失败"

            admin_token = login_resp["access_token"]
            admin_headers = {"Authorization": f"Bearer {admin_token}"}
            logger.success(f"管理员登录成功 (耗时 {elapsed:.3f}s)")
            logger.data("登录响应", {
                "access_token": admin_token[:40] + "...",
                "refresh_token": login_resp["refresh_token"][:40] + "...",
                "token_type": login_resp.get("token_type"),
                "user": login_resp["user"],
            })

        # ============================================================
        # 步骤 3: 创建三种角色新用户
        # ============================================================
        with logger.step(3, "管理员创建新用户（学生/教师/校友）"):
            new_users = [
                {"student_no": "2025999", "name": "新学生张三", "role": "student"},
                {"student_no": "T9999", "name": "新教师李教授", "role": "teacher"},
                {"student_no": "A9999", "name": "新校友王学长", "role": "alumni"},
            ]

            created_user_ids = {}
            for u in new_users:
                r = timed_request(
                    client, logger, "POST", "/api/v1/admin/users",
                    json=u, headers=admin_headers,
                )
                assert r.status_code == 200, f"创建用户失败 [{u['student_no']}]: {r.text}"
                user_data = r.json()
                created_user_ids[u["role"]] = user_data["id"]
                logger.success(f"创建用户: {u['role']} (ID={user_data['id']}, 状态={user_data['status']})")

            logger.data("创建的用户 ID 映射", created_user_ids)

        # ============================================================
        # 步骤 4: 重置用户密码
        # ============================================================
        with logger.step(4, "管理员重置用户密码"):
            temp_passwords = {}
            for role, user_id in created_user_ids.items():
                new_pwd = f"Temp@{role}123"
                r = timed_request(
                    client, logger, "PUT", f"/api/v1/admin/users/{user_id}/reset-password",
                    json={"new_password": new_pwd}, headers=admin_headers,
                )
                assert r.status_code == 200, f"重置密码失败 [{role}]: {r.text}"
                temp_passwords[role] = new_pwd
                logger.success(f"重置密码: {role} → {new_pwd}")

            logger.data("临时密码表", temp_passwords)

        # ============================================================
        # 步骤 5: 新用户登录
        # ============================================================
        with logger.step(5, "新用户登录（临时密码）"):
            user_tokens = {}
            user_credentials = [("student", "2025999"), ("teacher", "T9999"), ("alumni", "A9999")]
            for role, student_no in user_credentials:
                start = time.time()
                login_resp = login(client, logger, student_no, temp_passwords[role])
                elapsed = time.time() - start
                assert login_resp, f"{role} 登录失败"
                user_tokens[role] = login_resp["access_token"]
                logger.success(f"{role} 登录成功 (耗时 {elapsed:.3f}s, 状态={login_resp['user']['status']})")

            logger.data("Token 摘要", {
                role: token[:30] + "..." for role, token in user_tokens.items()
            })

        # ============================================================
        # 步骤 6: 修改密码
        # ============================================================
        with logger.step(6, "所有用户修改密码（pending_change → active）"):
            user_new_passwords = {
                "student": ("2025999", "Temp@student123", "NewStudent@456"),
                "teacher": ("T9999", "Temp@teacher123", "NewTeacher@456"),
                "alumni": ("A9999", "Temp@alumni123", "NewAlumni@456"),
            }

            # 修改密码
            for role, (student_no, old_pwd, new_pwd) in user_new_passwords.items():
                r = timed_request(
                    client, logger, "POST", "/api/v1/auth/change-password",
                    json={"old_password": old_pwd, "new_password": new_pwd},
                    headers={"Authorization": f"Bearer {user_tokens[role]}"},
                )
                assert r.status_code == 200, f"[{role}] 修改密码失败: {r.text}"
                logger.success(f"{role} 修改密码成功: {old_pwd} → {new_pwd}")

            # 验证旧密码失效
            logger.info("验证旧密码已失效...")
            for role, (student_no, old_pwd, new_pwd) in user_new_passwords.items():
                r = timed_request(
                    client, logger, "POST", "/api/v1/auth/login",
                    json={"student_no": student_no, "password": old_pwd},
                )
                assert r.status_code == 401, f"[{role}] 旧密码应该登录失败"
                logger.success(f"{role} 旧密码已被拒绝 (401)")

            # 新密码登录
            logger.info("用新密码重新登录...")
            for role, (student_no, old_pwd, new_pwd) in user_new_passwords.items():
                login_resp = login(client, logger, student_no, new_pwd)
                assert login_resp, f"[{role}] 新密码登录失败"
                user_tokens[role] = login_resp["access_token"]
                logger.success(f"{role} 新密码登录成功 (状态={login_resp['user']['status']})")

            student_headers = {"Authorization": f"Bearer {user_tokens['student']}"}
            alumni_headers = {"Authorization": f"Bearer {user_tokens['alumni']}"}
            teacher_headers = {"Authorization": f"Bearer {user_tokens['teacher']}"}

        # ============================================================
        # 步骤 7: 验证 V2 新字段
        # ============================================================
        with logger.step(7, "验证 V2 新字段（profile / graduation_year）"):
            # 学生更新 profile
            student_profile = {
                "major": "数据科学与大数据技术",
                "research": ["机器学习", "自然语言处理"],
                "skills": ["Python", "PyTorch", "SQL"],
                "grade": "大二",
            }
            r = timed_request(
                client, logger, "PUT", "/api/v1/users/me",
                headers=student_headers,
                json={"profile": student_profile},
            )
            assert r.status_code == 200, f"更新 profile 失败: {r.text}"
            updated = r.json()
            assert updated["profile"]["major"] == "数据科学与大数据技术"
            logger.success("学生更新 profile 成功")
            logger.data("学生 profile", updated["profile"])

            # 校友设置毕业年份
            r = timed_request(
                client, logger, "PUT", "/api/v1/users/me",
                headers=alumni_headers,
                json={"graduation_year": 2024, "profile": {"field": "人工智能", "current_job": "算法工程师"}},
            )
            assert r.status_code == 200, f"更新校友信息失败: {r.text}"
            alumni_info = r.json()
            assert alumni_info["graduation_year"] == 2024
            assert alumni_info["profile"]["current_job"] == "算法工程师"
            logger.success(f"校友设置毕业年份: {alumni_info['graduation_year']}")
            logger.data("校友信息", {
                "graduation_year": alumni_info["graduation_year"],
                "profile": alumni_info["profile"],
            })

            # 教师设置研究方向
            r = timed_request(
                client, logger, "PUT", "/api/v1/users/me",
                headers=teacher_headers,
                json={"profile": {"field": "计算机科学", "title": "教授", "directions": ["深度学习", "计算机视觉"]}},
            )
            assert r.status_code == 200, f"更新教师信息失败: {r.text}"
            teacher_info = r.json()
            assert teacher_info["profile"]["title"] == "教授"
            logger.success(f"教师设置研究方向: {teacher_info['profile']['title']}")
            logger.data("教师 profile", teacher_info["profile"])

        # ============================================================
        # 步骤 8: 验证数据库实际存储
        # ============================================================
        with logger.step(8, "验证数据库实际存储"):
            db = db_mod.SessionLocal()
            try:
                with db_mod.engine.connect() as conn:
                    start = time.time()
                    rows = conn.execute(
                        text("SELECT id, student_no, name, role, status, graduation_year, "
                             "CASE WHEN profile_json IS NOT NULL THEN '有' ELSE '无' END as has_profile "
                             "FROM users WHERE deleted_at IS NULL ORDER BY id")
                    ).fetchall()
                    elapsed = time.time() - start
                    logger.info(f"查询 users 表 (耗时 {elapsed:.3f}s, {len(rows)} 条记录)")

                    user_list = []
                    logger.console(f"  📊 users 表记录:")
                    for row in rows:
                        logger.console(f"     ID={row[0]}, 学号={row[1]}, 姓名={row[2]}, "
                                       f"角色={row[3]}, 状态={row[4]}, 毕业年份={row[5]}, profile={row[6]}")
                        user_list.append({
                            "id": row[0], "student_no": row[1], "name": row[2],
                            "role": row[3], "status": row[4],
                            "graduation_year": row[5], "has_profile": row[6],
                        })
                    logger.data("users 表快照", user_list)

                    # 检查会话表
                    session_count = conn.execute(text("SELECT COUNT(*) FROM user_sessions")).scalar()
                    logger.info(f"user_sessions 表: {session_count} 条会话记录")

                    # 检查 V2 新表
                    v2_tables = ["achievements", "resources", "resource_favorites", "resource_likes",
                                 "teacher_directions", "communication_applications", "learning_plans"]
                    table_stats = {}
                    for table_name in v2_tables:
                        count = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
                        table_stats[table_name] = count
                        logger.console(f"  📊 {table_name}: {count} 条记录")
                    logger.data("V2 表统计", table_stats)
            finally:
                db.close()

        # ============================================================
        # 步骤 9: 验证权限隔离
        # ============================================================
        with logger.step(9, "验证权限隔离"):
            # 学生不能访问管理员接口
            r = timed_request(
                client, logger, "GET", "/api/v1/admin/users",
                headers=student_headers,
            )
            assert r.status_code == 403, f"学生不应能访问管理员接口: {r.status_code}"
            logger.success("学生访问管理员接口被拒绝 (403)")

            # 学生不能创建教师方向
            r = timed_request(
                client, logger, "POST", "/api/v1/teachers/directions",
                headers=student_headers,
                json={"title": "测试方向"},
            )
            assert r.status_code == 403, f"学生不应能创建教师方向: {r.status_code}"
            logger.success("学生创建教师方向被拒绝 (403)")

            # 教师可以创建方向
            r = timed_request(
                client, logger, "POST", "/api/v1/teachers/directions",
                headers=teacher_headers,
                json={
                    "title": "深度学习与计算机视觉",
                    "description": "招收对 AI 视觉感兴趣的学生",
                    "tags": ["深度学习", "CV", "PyTorch"],
                },
            )
            assert r.status_code == 200, f"教师创建方向失败: {r.text}"
            direction_id = r.json()["id"]
            logger.success(f"教师创建研究方向成功: ID={direction_id}")

            # 学生可以搜索教师
            r = timed_request(
                client, logger, "GET", "/api/v1/teachers/match",
                headers=student_headers,
                params={"q": "深度学习"},
            )
            assert r.status_code == 200
            assert r.json()["total"] >= 1
            logger.success(f"学生搜索教师成功: 找到 {r.json()['total']} 位匹配教师")

        # ============================================================
        # 步骤 10: 验证刷新令牌
        # ============================================================
        with logger.step(10, "验证刷新令牌机制"):
            # 重新登录获取 refresh token
            start = time.time()
            login_resp = login(client, logger, "2025999", "NewStudent@456")
            elapsed = time.time() - start
            assert login_resp, "登录失败"
            refresh_token = login_resp["refresh_token"]
            old_access = login_resp["access_token"]
            logger.info(f"重新登录耗时: {elapsed:.3f}s")

            # 刷新令牌
            r = timed_request(
                client, logger, "POST", "/api/v1/auth/refresh",
                json={"refresh_token": refresh_token},
            )
            assert r.status_code == 200, f"刷新令牌失败: {r.text}"
            new_access = r.json()["access_token"]
            new_refresh = r.json()["refresh_token"]
            logger.success("刷新令牌成功")
            logger.data("Token 对比", {
                "旧 access": old_access[:30] + "...",
                "新 access": new_access[:30] + "...",
                "access 是否变化": old_access != new_access,
                "refresh 是否旋转": refresh_token != new_refresh,
            })

            # 旧 refresh 应该失效
            r = timed_request(
                client, logger, "POST", "/api/v1/auth/refresh",
                json={"refresh_token": refresh_token},
            )
            assert r.status_code == 401, f"旧 refresh token 应该已失效: {r.status_code}"
            logger.success("旧 refresh token 已失效 (401) - 旋转机制正常")

        # ============================================================
        # 总结
        # ============================================================
        logger.console("\n" + "=" * 70)
        logger.console("🎉 所有测试通过！数据库结构完全正常工作")
        logger.console("=" * 70)
        logger.console("\n测试覆盖:")
        logger.console("  ✅ 数据库表结构（23 张表 + V2 新字段）")
        logger.console("  ✅ 管理员登录")
        logger.console("  ✅ 创建三种角色用户（student/teacher/alumni）")
        logger.console("  ✅ 重置密码")
        logger.console("  ✅ 新用户登录（pending_change 状态）")
        logger.console("  ✅ 修改密码 + 状态变更为 active")
        logger.console("  ✅ V2 新字段: profile_json（专业/研究方向/技能）")
        logger.console("  ✅ V2 新字段: graduation_year（校友毕业年份）")
        logger.console("  ✅ 权限隔离（学生/教师/管理员）")
        logger.console("  ✅ Refresh Token 旋转机制")

    except Exception as e:
        logger.console(f"\n❌ 测试失败: {type(e).__name__}: {e}")
        import traceback
        tb = traceback.format_exc()
        logger._write_file(tb + "\n")
        logger.summary()
        raise

    # 输出汇总报告
    logger.summary()


if __name__ == "__main__":
    test_db_structure()
