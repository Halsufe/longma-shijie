import asyncio
import json
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.ai.skill_dispatcher import SKILL_TRIGGERS, SkillDispatcher, skill_dispatcher
from backend.app.ai.skills import get_skill_prompt
from backend.app.models.skill import Skill
from backend.app.repositories.skill_repo import SYSTEM_SKILLS, SkillRepository
from backend.app.services import chat_service
from backend.app.services.chat_service import BUSINESS_SKILL_NAMES, ChatService, _check_skill_permission


EXPECTED_BUSINESS_SKILLS = {
    "competition_recommend": ["@竞赛推荐", "@比赛推荐", "@推荐比赛", "@competition"],
    "mentor_match": ["@导师匹配", "@找导师", "@匹配导师", "@mentor"],
    "party_query": ["@党建查询", "@党建", "@党员查询", "@party"],
    "achievement_manage": ["@成果管理", "@我的成果", "@成果录入", "@achievement"],
}


def _skill_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Skill.__table__.create(engine)
    return sessionmaker(bind=engine, future=True)()


def test_business_skill_seed_data_is_complete_and_idempotent():
    db = _skill_session()
    try:
        assert SkillRepository.seed_system_skills(db) == len(SYSTEM_SKILLS)
        assert SkillRepository.seed_system_skills(db) == 0

        skills = {skill.name: skill for skill in SkillRepository.list(db)}
        for name, triggers in EXPECTED_BUSINESS_SKILLS.items():
            skill = skills[name]
            assert skill.category == "business"
            assert skill.is_enabled is True
            assert skill.is_system is True
            assert json.loads(skill.triggers) == triggers

        assert len(skills) == len(SYSTEM_SKILLS)
    finally:
        db.close()


def test_business_fallback_triggers_resolve_and_strip_prefix():
    dispatcher = SkillDispatcher()
    for skill_name, triggers in EXPECTED_BUSINESS_SKILLS.items():
        for trigger in triggers:
            assert SKILL_TRIGGERS[trigger] == skill_name
            assert dispatcher.parse_skill(f"  {trigger} 测试需求  ") == (skill_name, "测试需求")


def test_existing_skill_trigger_and_prompt_behavior_is_unchanged():
    dispatcher = SkillDispatcher()
    expected = {
        "@思维导图": "mindmap",
        "@翻译": "translate",
        "@代码解释": "code_explain",
        "@代码生成": "code_generate",
        "@总结": "summary",
        "@润色": "polish",
        "@查数": "db_query",
        "@管理": "db_manage",
    }
    for trigger, skill_name in expected.items():
        assert dispatcher.parse_skill(f"{trigger} 原有需求") == (skill_name, "原有需求")
        assert get_skill_prompt(skill_name, "原有需求")


def test_database_registration_order_wins_for_duplicate_trigger():
    db = _skill_session()
    try:
        db.add_all(
            [
                Skill(
                    name="first",
                    display_name="First",
                    triggers='["@same"]',
                    category="business",
                    is_enabled=True,
                    is_system=True,
                ),
                Skill(
                    name="second",
                    display_name="Second",
                    triggers='["@same"]',
                    category="business",
                    is_enabled=True,
                    is_system=True,
                ),
            ]
        )
        db.commit()

        assert SkillDispatcher().parse_skill("@same input", db) == ("first", "input")
    finally:
        db.close()


def test_disabled_business_skill_is_not_restored_by_fallback_mapping():
    db = _skill_session()
    try:
        SkillRepository.seed_system_skills(db)
        skill = SkillRepository.get_by_name(db, "competition_recommend")
        assert skill is not None
        SkillRepository.update(db, skill, is_enabled=False)

        assert SkillDispatcher().parse_skill("@竞赛推荐 测试", db) == (None, "@竞赛推荐 测试")
    finally:
        db.close()


def test_empty_database_trigger_map_does_not_enable_fallback_skills():
    db = _skill_session()
    try:
        assert SkillDispatcher().parse_skill("@竞赛推荐 测试", db) == (None, "@竞赛推荐 测试")
    finally:
        db.close()


def test_business_prompt_builders_are_registered_and_specific():
    expected_terms = {
        "competition_recommend": "已截止比赛",
        "mentor_match": "研究方向",
        "party_query": "只读",
        "achievement_manage": "确认令牌",
    }
    for skill_name, expected_term in expected_terms.items():
        prompt = get_skill_prompt(skill_name, "测试输入")
        assert "测试输入" in prompt
        assert expected_term in prompt


def test_business_skill_permission_defers_resource_checks_to_executor():
    for skill_name in BUSINESS_SKILL_NAMES:
        assert _check_skill_permission(SimpleNamespace(), 123, skill_name) == (True, "")


def test_simple_chat_routes_business_skill_without_using_generic_adapter(monkeypatch):
    messages = iter([SimpleNamespace(id=11), SimpleNamespace(id=12)])
    monkeypatch.setattr(chat_service.ChatRepository, "add_message", lambda *args, **kwargs: next(messages))
    monkeypatch.setattr(
        chat_service,
        "_execute_business_skill",
        lambda *args, **kwargs: _async_result({"response": "结构化业务回复", "items": [{"id": 1}]}),
    )
    monkeypatch.setattr(chat_service, "get_adapter", lambda: (_ for _ in ()).throw(AssertionError("generic adapter used")))

    result = asyncio.run(
        ChatService.send_message_simple(
            SimpleNamespace(),
            session_id=1,
            user_content="@竞赛推荐 人工智能",
            user_id=7,
            rag_scope="none",
        )
    )

    assert result["ai_message"]["skill"] == "competition_recommend"
    assert result["ai_message"]["content"] == "结构化业务回复"
    assert result["ai_message"]["structured_result"]["items"] == [{"id": 1}]


def test_stream_chat_routes_business_skill_without_generic_prompt_path(monkeypatch):
    messages = iter([SimpleNamespace(id=21), SimpleNamespace(id=22)])
    monkeypatch.setattr(chat_service.ChatRepository, "add_message", lambda *args, **kwargs: next(messages))
    monkeypatch.setattr(
        chat_service,
        "_execute_business_skill",
        lambda *args, **kwargs: _async_result({"reply": "业务流式回复", "total": 2}),
    )
    monkeypatch.setattr(chat_service, "get_adapter", lambda: (_ for _ in ()).throw(AssertionError("generic adapter used")))

    async def collect_events():
        return [
            event
            async for event in ChatService.send_message_stream(
                SimpleNamespace(),
                session_id=1,
                user_content="@导师匹配 大语言模型项目",
                user_id=7,
                rag_scope="none",
            )
        ]

    events = asyncio.run(collect_events())
    assert [event["type"] for event in events] == ["user_msg", "chunk", "done"]
    assert events[1]["data"] == "业务流式回复"
    assert events[2]["data"]["structured_result"]["total"] == 2


def test_agent_prefix_has_priority_over_business_trigger(monkeypatch):
    messages = iter([SimpleNamespace(id=31), SimpleNamespace(id=32)])

    class FakeAgent:
        def __init__(self, *args, **kwargs):
            pass

        async def chat(self, content):
            assert content == "@竞赛推荐 人工智能"
            return "Agent 回复"

        def get_memory_stats(self):
            return {"conversation_messages": 1}

    monkeypatch.setattr(chat_service, "LongmaAgent", FakeAgent)
    monkeypatch.setattr(chat_service.ChatRepository, "add_message", lambda *args, **kwargs: next(messages))
    monkeypatch.setattr(
        skill_dispatcher,
        "parse_skill",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Skill dispatcher used before Agent")),
    )
    chat_service._agent_sessions.clear()
    chat_service._agent_memories.clear()

    result = asyncio.run(
        ChatService.send_message_simple(
            SimpleNamespace(),
            session_id=1,
            user_content="@agent @竞赛推荐 人工智能",
            user_id=7,
            rag_scope="none",
        )
    )

    assert result["ai_message"]["skill"] == "agent"
    assert result["ai_message"]["content"] == "Agent 回复"


async def _async_result(value):
    return value
