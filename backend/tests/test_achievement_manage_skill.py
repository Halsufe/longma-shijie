import asyncio
import json
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.ai.business_skills.achievement_manage import AchievementManageExecutor
from backend.app.ai.business_skills.service import BusinessSkillService
from backend.app.core.confirmation import ConfirmationManager, require_confirmation_token
from backend.app.core.database import Base
from backend.app.core.errors import AppException
from backend.app.models.audit import AuditLog
from backend.app.models.skill import SkillCall
from backend.app.models.user import User
from backend.app.repositories.achievement_repo import AchievementRepository
from backend.app.services.achievement_files import AchievementFileService
from backend.app.services.achievement_templates import ACHIEVEMENT_TEMPLATES


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _user(db, student_no):
    user = User(
        student_no=student_no,
        name=student_no,
        password_hash="hash",
        role="student",
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _paper_details():
    year = datetime.now().year
    return {
        "authors": "张三",
        "journal": "Management Science",
        "sci_indexed": True,
        "ssci_indexed": False,
        "cssci_indexed": False,
        "is_top_journal": False,
        "paper_type": "期刊论文",
        "pub_year": year,
        "pub_month": 6,
        "wos_url": "https://example.com/paper",
        "volume": "1",
        "issue": "1",
        "citation_count": 0,
        "research_direction": "机器学习",
        "pages": "1-10",
        "keywords": "机器学习,摘要",
        "doi": "10.1/example",
        "abstract": "摘要",
    }


def test_confirmation_helper_rejects_missing_wrong_user_and_changed_data():
    data = {"title": "成果"}
    token = ConfirmationManager.create_confirmation(1, "achievement.create", data)["confirmation_token"]
    assert require_confirmation_token("achievement.create", token, data, 1) == {"valid": True}
    with pytest.raises(AppException) as missing:
        require_confirmation_token("achievement.create", None, data, 1)
    assert missing.value.code == "CONFIRMATION_REQUIRED"
    with pytest.raises(AppException):
        require_confirmation_token("achievement.create", token, data, 2)
    with pytest.raises(AppException):
        require_confirmation_token("achievement.create", token, {"title": "已变更"}, 1)


def test_query_is_owner_scoped_and_templates_cover_eight_categories(db):
    owner = _user(db, "OWNER")
    other = _user(db, "OTHER")
    own = AchievementRepository.create(db, owner.id, category="paper", title="本人成果")
    AchievementRepository.create(db, other.id, category="paper", title="他人成果")
    executor = AchievementManageExecutor()

    listed = asyncio.run(executor.execute("我的成果", owner, db))
    assert listed["total"] == 1
    assert listed["items"][0]["id"] == own.id
    templates = asyncio.run(executor.execute("成果模板需要哪些字段", owner, db))
    assert set(templates["templates"]) == set(ACHIEVEMENT_TEMPLATES)
    assert templates["total"] == 8


def test_create_requires_proof_then_preview_confirm_audit_and_skill_call(db, monkeypatch):
    owner = _user(db, "CREATE")
    executor = AchievementManageExecutor()
    missing = asyncio.run(executor.execute('新增成果 {"category":"paper","title":"论文"}', owner, db))
    assert missing["status"] == "needs_proof"
    assert db.query(SkillCall).count() == 0

    monkeypatch.setattr(AchievementFileService, "validate_owned", staticmethod(lambda *args: None))
    payload = {
        "category": "paper",
        "title": "论文成果",
        "details": _paper_details(),
        "proofs": [{"stored_name": "proof.pdf", "name": "proof.pdf", "size": 10}],
    }
    request = "新增成果 " + json.dumps(payload, ensure_ascii=False)
    preview = asyncio.run(BusinessSkillService.execute("achievement_manage", request, owner, db))
    assert preview["data"]["status"] == "pending_confirmation"
    payload["confirmation_token"] = preview["data"]["confirmation_token"]
    confirmed_request = "新增成果 " + json.dumps(payload, ensure_ascii=False)
    result = asyncio.run(BusinessSkillService.execute("achievement_manage", confirmed_request, owner, db))

    assert result["data"]["status"] == "success"
    assert result["data"]["item"]["status"] == "pending"
    assert db.query(SkillCall).filter(SkillCall.skill_name == "achievement_manage").count() == 2
    audit = db.query(AuditLog).filter(AuditLog.action == "achievement.create").one()
    assert audit.result == "success"
    assert preview["data"]["confirmation_token"] not in (audit.detail or "")


def test_update_resets_pending_delete_is_soft_and_other_owner_is_hidden(db):
    owner = _user(db, "EDIT")
    other = _user(db, "OUTSIDER")
    item = AchievementRepository.create(
        db, owner.id, category="paper", title="旧标题", status="approved"
    )
    executor = AchievementManageExecutor()

    update_data = {"achievement_id": item.id, "title": "新标题"}
    update_preview = asyncio.run(
        executor.execute("修改成果 " + json.dumps(update_data, ensure_ascii=False), owner, db)
    )
    update_data["confirmation_token"] = update_preview["confirmation_token"]
    updated = asyncio.run(
        executor.execute("修改成果 " + json.dumps(update_data, ensure_ascii=False), owner, db)
    )
    assert updated["item"]["title"] == "新标题"
    assert updated["item"]["status"] == "pending"

    with pytest.raises(AppException):
        asyncio.run(
            executor.execute(
                "修改成果 " + json.dumps({"achievement_id": item.id, "title": "越权"}, ensure_ascii=False),
                other,
                db,
            )
        )

    delete_data = {"achievement_id": item.id}
    delete_preview = asyncio.run(
        executor.execute("删除成果 " + json.dumps(delete_data, ensure_ascii=False), owner, db)
    )
    delete_data["confirmation_token"] = delete_preview["confirmation_token"]
    deleted = asyncio.run(
        executor.execute("删除成果 " + json.dumps(delete_data, ensure_ascii=False), owner, db)
    )
    assert deleted["status"] == "success"
    assert AchievementRepository.get_by_id(db, item.id) is None
    assert db.query(type(item)).filter(type(item).id == item.id).one().deleted_at is not None
