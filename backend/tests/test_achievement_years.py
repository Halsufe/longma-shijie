from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import Depends, Header
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.api.deps import get_current_user
from backend.app.core.database import Base, get_db
from backend.app.models.user import User


@pytest.fixture()
def client(tmp_path: Path):
    from backend.app.core import config as cfg
    from backend.app.core import database as db_mod

    previous_engine = db_mod.engine
    previous_session_local = db_mod.SessionLocal
    previous_storage_path = cfg.settings.STORAGE_PATH
    previous_environment = cfg.settings.ENV

    db_mod.engine = create_engine(
        f"sqlite:///{tmp_path / 'achievement-years.db'}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    db_mod.SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=db_mod.engine,
        future=True,
    )
    cfg.settings.STORAGE_PATH = str(tmp_path / "storage")
    cfg.settings.ENV = "test"

    from backend.app.main import create_app

    app = create_app()
    Base.metadata.create_all(bind=db_mod.engine)
    db = db_mod.SessionLocal()
    db.add_all([
        User(student_no="s1", name="学生一", password_hash="unused", role="student", status="active"),
        User(student_no="s2", name="学生二", password_hash="unused", role="student", status="active"),
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

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        db_mod.engine.dispose()
        db_mod.engine = previous_engine
        db_mod.SessionLocal = previous_session_local
        cfg.settings.STORAGE_PATH = previous_storage_path
        cfg.settings.ENV = previous_environment


def _create(
    client: TestClient,
    category: str,
    date: str | None,
    *,
    user: str = "s1",
) -> dict:
    response = client.post(
        "/api/v1/achievements",
        json={
            "category": category,
            "title": f"{category}-{date or '无日期'}",
            "achievement_date": date,
        },
        headers={"X-Test-User": user},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_years_route_empty_and_not_captured_by_dynamic_route(client: TestClient) -> None:
    response = client.get("/api/v1/achievements/years", headers={"X-Test-User": "s1"})

    assert response.status_code == 200
    assert response.json() == []


def test_years_are_descending_counted_and_isolated(client: TestClient) -> None:
    first = _create(client, "paper", "2026-06")
    _create(client, "award", "2026-09")
    _create(client, "social", "2024-01")
    _create(client, "arts", None)
    _create(client, "research", "not-a-year")
    _create(client, "patent", "2028-03", user="s2")

    deleted = client.delete(
        f"/api/v1/achievements/{first['id']}",
        headers={"X-Test-User": "s1"},
    )
    assert deleted.status_code == 200

    response = client.get("/api/v1/achievements/years", headers={"X-Test-User": "s1"})

    assert response.status_code == 200
    assert response.json() == [
        {"year": 2026, "count": 1},
        {"year": 2024, "count": 1},
    ]


def test_year_filter_works_across_categories_and_without_year_returns_all(client: TestClient) -> None:
    paper = _create(client, "paper", "2025-12")
    award = _create(client, "award", "2025-03")
    _create(client, "organization", "2024-07")

    filtered = client.get(
        "/api/v1/achievements?year=2025",
        headers={"X-Test-User": "s1"},
    )
    unfiltered = client.get("/api/v1/achievements", headers={"X-Test-User": "s1"})
    invalid = client.get(
        "/api/v1/achievements?year=25",
        headers={"X-Test-User": "s1"},
    )

    assert filtered.status_code == 200
    assert [item["id"] for item in filtered.json()["items"]] == [paper["id"], award["id"]]
    assert unfiltered.status_code == 200
    assert unfiltered.json()["total"] == 3
    assert invalid.status_code == 422


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is required for frontend component tests")
def test_timeline_interaction_doi_and_list_event_interfaces(tmp_path: Path) -> None:
    module_dir = tmp_path / "modules"
    module_dir.mkdir()
    for filename in (
        "achievement_timeline.js",
        "achievement_list.js",
        "achievement_templates.js",
        "ui.js",
    ):
        shutil.copy(PROJECT_ROOT / "frontend" / "js" / filename, module_dir / filename)
    (module_dir / "package.json").write_text('{"type":"module"}', encoding="utf-8")
    runner = module_dir / "runner.mjs"
    runner.write_text(
        """
import assert from "node:assert/strict";
import { bindAchievementTimeline, renderAchievementTimeline } from "./achievement_timeline.js";
import { bindAchievementList, getAchievementDoiUrl, renderAchievementList } from "./achievement_list.js";

const timeline = renderAchievementTimeline([{ year: 2024, count: 2 }], "2026", 2026);
assert.match(timeline, /data-achievement-year="all"/);
assert.match(timeline, /data-achievement-year="2026"/);
assert.match(timeline, /data-achievement-year="2024"/);

const makeNode = dataset => ({
  dataset,
  addEventListener(type, listener) { this.listener = listener; },
  removeEventListener() {},
});
const yearNode = makeNode({ achievementYear: "2024" });
let selectedYear;
bindAchievementTimeline({ querySelectorAll: () => [yearNode] }, value => { selectedYear = value; });
yearNode.listener();
assert.equal(selectedYear, "2024");

const paper = {
  id: 7,
  category: "paper",
  title: "论文标题",
  achievement_date: "2025-06",
  level: null,
  status: "approved",
  proofs: [{ id: "one" }, { id: "two" }],
  details: { doi: "10.1000/example" },
};
assert.equal(getAchievementDoiUrl(paper), "https://doi.org/10.1000/example");
const list = renderAchievementList([paper]);
assert.ok(list.includes('href="https://doi.org/10.1000/example"'));
assert.match(list, /附件<\/b>2 份/);
assert.doesNotMatch(renderAchievementList([{ ...paper, details: { doi: "无" } }]), /achievement-doi-link/);

const nodes = {
  "[data-view-achievement]": makeNode({ viewAchievement: "7" }),
  "[data-edit-achievement]": makeNode({ editAchievement: "7" }),
  "[data-delete-achievement]": makeNode({ deleteAchievement: "7" }),
};
const events = [];
bindAchievementList(
  { querySelectorAll: selector => [nodes[selector]] },
  { onView: id => events.push(["view", id]), onEdit: id => events.push(["edit", id]), onDelete: id => events.push(["delete", id]) },
);
Object.values(nodes).forEach(node => node.listener());
assert.deepEqual(events, [["view", 7], ["edit", 7], ["delete", 7]]);
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [shutil.which("node") or "node", str(runner)],
        cwd=module_dir,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
