import asyncio
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.ai.agent_tools import AgentTools
from backend.app.ai.business_skills import BUSINESS_SKILL_REGISTRY
from backend.app.ai.business_skills.base import (
    BusinessSkillExecutor,
    BusinessSkillPermissionError,
)
from backend.app.ai.business_skills.service import BusinessSkillService
from backend.app.models.skill import SkillCall
from backend.app.models.user import User, UserStatus
from backend.app.services import chat_service
from backend.app.services.chat_service import ChatService


EXPECTED_SKILLS = {
    "competition_recommend",
    "mentor_match",
    "party_query",
    "achievement_manage",
}


def _business_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    User.__table__.create(engine)
    SkillCall.__table__.create(engine)
    return sessionmaker(bind=engine, future=True)()


def _create_user(db, *, role="student"):
    user = User(
        student_no=f"M2-{role}",
        name="M2 Tester",
        password_hash="not-used",
        role=role,
        status=UserStatus.ACTIVE.value,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_registry_maps_all_business_skills_to_executor_classes():
    assert set(BUSINESS_SKILL_REGISTRY) == EXPECTED_SKILLS
    assert all(issubclass(executor, BusinessSkillExecutor) for executor in BUSINESS_SKILL_REGISTRY.values())


def test_service_executes_and_records_success():
    db = _business_session()
    try:
        user = _create_user(db)
        result = asyncio.run(BusinessSkillService.execute("competition_recommend", "人工智能 前3", user, db))

        assert result["skill_name"] == "competition_recommend"
        assert result["data"]["limit"] == 3
        assert result["response"]

        call = db.query(SkillCall).one()
        assert call.skill_name == "competition_recommend"
        assert call.user_id == user.id
        assert call.input == "人工智能 前3"
        assert call.output and "competition_recommend" in call.output
        assert call.status == "success"
        assert call.duration_ms is not None
    finally:
        db.close()


def test_service_records_executor_failure(monkeypatch):
    class FailingExecutor(BusinessSkillExecutor):
        skill_name = "competition_recommend"

        async def execute(self, user_input, user, db):
            raise RuntimeError("executor failed")

    db = _business_session()
    try:
        user = _create_user(db)
        monkeypatch.setitem(BUSINESS_SKILL_REGISTRY, "competition_recommend", FailingExecutor)

        with pytest.raises(RuntimeError, match="executor failed"):
            asyncio.run(BusinessSkillService.execute("competition_recommend", "测试异常", user, db))

        call = db.query(SkillCall).one()
        assert call.status == "failed"
        assert call.output and "executor failed" in call.output
        assert call.error == "executor failed"
        assert call.duration_ms is not None
    finally:
        db.close()


def test_party_permission_denial_is_recorded():
    db = _business_session()
    try:
        user = _create_user(db)

        with pytest.raises(BusinessSkillPermissionError, match="仅管理员"):
            asyncio.run(BusinessSkillService.execute("party_query", "查询全部党员名册", user, db))

        call = db.query(SkillCall).one()
        assert call.skill_name == "party_query"
        assert call.user_id == user.id
        assert call.status == "failed"
        assert call.output and "仅管理员" in call.output
        assert call.error and "仅管理员" in call.error
    finally:
        db.close()


def test_agent_tool_uses_same_business_service(monkeypatch):
    calls = []

    async def fake_execute(skill_name, user_input, user, db):
        calls.append((skill_name, user_input, user.id, db))
        return {"skill_name": skill_name, "response": "业务结果", "data": {"items": []}}

    monkeypatch.setattr(BusinessSkillService, "execute", fake_execute)
    tools = AgentTools(SimpleNamespace(), user_id=8)
    tools._user = SimpleNamespace(id=8, role="student")

    raw_result = asyncio.run(tools.recommend_competitions("人工智能"))

    assert json.loads(raw_result)["skill_name"] == "competition_recommend"
    assert calls == [("competition_recommend", "人工智能", 8, tools.db)]
    assert tools.business_skill_names == ["competition_recommend"]


def test_agent_business_call_is_not_recorded_as_generic_agent(monkeypatch):
    messages = iter([SimpleNamespace(id=31), SimpleNamespace(id=32)])
    generic_calls = []

    class FakeAgent:
        def __init__(self, *args, **kwargs):
            self.tools = SimpleNamespace(business_skill_names=["mentor_match"])

        async def chat(self, content):
            return "导师匹配业务回复"

        def get_memory_stats(self):
            return {"conversation_messages": 1}

    monkeypatch.setattr(chat_service, "LongmaAgent", FakeAgent)
    monkeypatch.setattr(chat_service.ChatRepository, "add_message", lambda *args, **kwargs: next(messages))
    monkeypatch.setattr(
        "backend.app.repositories.skill_repo.SkillCallRepository.create",
        lambda *args, **kwargs: generic_calls.append(kwargs),
    )
    chat_service._agent_sessions.clear()
    chat_service._agent_memories.clear()

    result = asyncio.run(
        ChatService.send_message_simple(
            SimpleNamespace(),
            session_id=1,
            user_content="@agent 帮我匹配导师",
            user_id=7,
            rag_scope="none",
        )
    )

    assert result["ai_message"]["skill"] == "mentor_match"
    assert generic_calls == []
