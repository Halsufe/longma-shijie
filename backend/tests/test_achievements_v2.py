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
from sqlalchemy.pool import StaticPool


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.api.deps import get_current_user
from backend.app.core.database import Base, get_db
from backend.app.models.user import User
from backend.app.services.achievement_service import (
    AchievementValidationError,
    validate_details,
)


CURRENT_YEAR = datetime.now().year
PREVIOUS_YEAR = CURRENT_YEAR - 1


def _achievement_payloads() -> dict[str, tuple[dict, str]]:
    return {
        "paper": ({
            "authors": "张三, 李四（通讯）", "journal": "Management Science",
            "sci_indexed": True, "ssci_indexed": "否", "cssci_indexed": False,
            "is_top_journal": "是", "paper_type": "期刊论文",
            "pub_year": CURRENT_YEAR, "pub_month": 6,
            "wos_url": "https://www.webofscience.com/example", "volume": "42",
            "issue": "3", "citation_count": 15, "research_direction": "数据智能",
            "pages": "20-30", "keywords": "数据挖掘, 决策分析",
            "doi": "10.1000/example", "abstract": "论文摘要",
        }, f"{CURRENT_YEAR}-06"),
        "award": ({
            "award_grade": "一等奖", "organizer": "全国竞赛组委会",
            "award_year": CURRENT_YEAR, "award_month": 9,
            "teacher_names": "王老师, 李老师", "is_team": True,
            "is_leader": "是", "member_names": "张三, 李四", "description": "获奖说明",
        }, f"{CURRENT_YEAR}-09"),
        "research": ({
            "project_unit": "龙马学院", "project_field": "人工智能",
            "project_funding": "5.00", "leader_name": "张三",
            "participant_names": "张三, 李四", "project_year": PREVIOUS_YEAR,
            "start_year": PREVIOUS_YEAR, "start_month": 3,
            "end_year": CURRENT_YEAR, "end_month": 12, "approval_no": "XM-001",
        }, f"{PREVIOUS_YEAR}-03"),
        "patent": ({
            "patent_type": "发明专利", "participant_names": "张三, 李四",
            "field": "人工智能", "apply_year": PREVIOUS_YEAR, "apply_month": 6,
            "grant_year": "无", "grant_month": "无", "application_no": "CN-001",
            "grant_no": "无", "abstract": "专利摘要",
        }, f"{PREVIOUS_YEAR}-06"),
        "innovation": ({
            "project_category": "创新项目", "leader_name": "张三",
            "member_names": "张三, 李四", "teacher_names": "王老师",
            "start_year": PREVIOUS_YEAR, "start_month": 4,
            "end_year": "进行中", "end_month": "进行中", "summary": "项目简介",
        }, f"{PREVIOUS_YEAR}-04"),
        "organization": ({
            "position": "部长", "assessment": "优秀", "honor_title": "优秀干部",
            "start_year": PREVIOUS_YEAR, "start_month": 5,
            "end_year": "进行中", "end_month": "进行中",
        }, f"{PREVIOUS_YEAR}-05"),
        "social": ({
            "practice_unit": "社区服务中心", "is_team": "是",
            "member_names": "张三, 李四", "is_leader": True,
            "start_year": CURRENT_YEAR, "start_month": 1,
            "end_year": CURRENT_YEAR, "end_month": 2,
            "process_description": "社会实践过程",
        }, f"{CURRENT_YEAR}-01"),
        "arts": ({
            "organizer": "校团委", "start_year": CURRENT_YEAR, "start_month": 7,
            "end_year": CURRENT_YEAR, "end_month": 8, "summary": "文体活动概述",
        }, f"{CURRENT_YEAR}-07"),
    }


LEVELS = {
    "award": "国家级",
    "research": "省级",
    "innovation": "校级",
    "arts": "校级",
}


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    from backend.app.core import config as cfg
    from backend.app.core import database as db_mod

    cfg.settings.DB_URL = "sqlite:///:memory:"
    cfg.settings.ENV = "test"
    cfg.settings.API_RATE_LIMIT = 100000
    previous_storage_path = cfg.settings.STORAGE_PATH
    cfg.settings.STORAGE_PATH = str(tmp_path / "storage")

    db_mod.engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    db_mod.SessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=db_mod.engine, future=True
    )

    from backend.app.main import create_app

    app = create_app()
    Base.metadata.create_all(bind=db_mod.engine)
    db = db_mod.SessionLocal()
    db.add_all([
        User(student_no="s1", name="学生一", password_hash="unused", role="student", status="active"),
        User(student_no="s2", name="学生二", password_hash="unused", role="student", status="active"),
        User(student_no="admin", name="管理员", password_hash="unused", role="admin", status="active"),
    ])
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

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    cfg.settings.STORAGE_PATH = previous_storage_path


def _create(client: TestClient, category: str, *, user: str = "s1", details: dict | None = None):
    template_details, _ = _achievement_payloads()[category]
    headers = {"X-Test-User": user}
    uploaded = client.post(
        "/api/v1/achievements/files",
        files={
            "file": (
                f"{category}-proof.pdf",
                b"%PDF-1.7 achievement proof",
                "application/pdf",
            )
        },
        headers=headers,
    )
    assert uploaded.status_code == 200, uploaded.text
    payload = {
        "category": category,
        "title": f"{category}-成果",
        "details": details if details is not None else template_details,
        "proofs": [uploaded.json()],
        "is_public": True,
    }
    if category in LEVELS:
        payload["level"] = LEVELS[category]
    return client.post("/api/v1/achievements", json=payload, headers=headers)


@pytest.mark.parametrize("category", list(_achievement_payloads()))
def test_create_all_eight_categories_with_derived_date(client: TestClient, category: str):
    response = _create(client, category)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["details"]
    assert len(body["proofs"]) == 1
    assert body["achievement_date"] == _achievement_payloads()[category][1]


@pytest.mark.parametrize("category", list(_achievement_payloads()))
def test_each_template_rejects_missing_required_field(category: str):
    details = _achievement_payloads()[category][0].copy()
    missing_key = next(iter(details))
    details.pop(missing_key)

    with pytest.raises(AchievementValidationError) as exc_info:
        validate_details(category, details)

    assert f"details.{missing_key}" in exc_info.value.errors


def test_field_level_enum_and_format_errors(client: TestClient):
    details = _achievement_payloads()["paper"][0].copy()
    details.update({"paper_type": "非法类型", "pub_month": 13, "wos_url": "not-a-url"})
    response = _create(client, "paper", details=details)

    assert response.status_code == 422
    message = response.json()["error"]["message"]
    assert "details.paper_type" in message
    assert "details.pub_month" in message
    assert "details.wos_url" in message


def test_update_revalidates_details_and_rederives_date(client: TestClient):
    created = _create(client, "paper").json()
    details = created["details"]
    details["pub_month"] = 12

    response = client.put(
        f"/api/v1/achievements/{created['id']}",
        json={"details": details},
        headers={"X-Test-User": "s1"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["achievement_date"] == f"{CURRENT_YEAR}-12"
    assert response.json()["details"]["pub_month"] == 12


def test_filters_sorting_and_static_public_route(client: TestClient):
    current = _create(client, "award").json()
    previous_details = _achievement_payloads()["award"][0].copy()
    previous_details["award_year"] = PREVIOUS_YEAR
    previous = _create(client, "award", details=previous_details).json()
    _create(client, "organization")

    response = client.get(
        f"/api/v1/achievements?year={CURRENT_YEAR}&category=award&status=pending",
        headers={"X-Test-User": "s1"},
    )
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [current["id"]]

    response = client.get("/api/v1/achievements", headers={"X-Test-User": "s1"})
    dates = [item["achievement_date"] for item in response.json()["items"]]
    assert dates == sorted(dates, reverse=True)

    approved = client.put(
        f"/api/v1/achievements/admin/{previous['id']}/approve",
        headers={"X-Test-User": "admin"},
    )
    assert approved.status_code == 200
    public = client.get("/api/v1/achievements/public/list", headers={"X-Test-User": "s1"})
    assert public.status_code == 200
    assert [item["id"] for item in public.json()["items"]] == [previous["id"]]


def test_owner_isolation_admin_detail_and_soft_delete(client: TestClient):
    achievement_id = _create(client, "social").json()["id"]
    path = f"/api/v1/achievements/{achievement_id}"

    assert client.get(path, headers={"X-Test-User": "s2"}).status_code == 404
    assert client.put(path, json={"title": "越权修改"}, headers={"X-Test-User": "s2"}).status_code == 404
    assert client.delete(path, headers={"X-Test-User": "s2"}).status_code == 404
    assert client.get(path, headers={"X-Test-User": "admin"}).status_code == 200

    deleted = client.delete(path, headers={"X-Test-User": "s1"})
    assert deleted.status_code == 200
    assert client.get(path, headers={"X-Test-User": "s1"}).status_code == 404
    assert client.get("/api/v1/achievements", headers={"X-Test-User": "s1"}).json()["total"] == 0


def test_legacy_request_without_details_or_proofs_remains_compatible(client: TestClient):
    response = client.post(
        "/api/v1/achievements",
        json={
            "category": "award",
            "title": "旧格式成果",
            "description": "旧格式描述",
            "achievement_date": "2024-11",
            "level": "国家级",
            "is_public": False,
        },
        headers={"X-Test-User": "s1"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["details"] == {}
    assert body["proofs"] == []
    assert body["achievement_date"] == "2024-11"

    updated = client.put(
        f"/api/v1/achievements/{body['id']}",
        json={"description": "兼容更新"},
        headers={"X-Test-User": "s1"},
    )
    assert updated.status_code == 200
    assert updated.json()["description"] == "兼容更新"
    assert updated.json()["details"] == {}
