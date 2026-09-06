import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.ai.agent_tools import AgentTools
from backend.app.ai.business_skills.base import BusinessSkillPermissionError
from backend.app.ai.business_skills.party_query import PartyQueryExecutor
from backend.app.ai.retriever import RAGService
from backend.app.core.database import Base
from backend.app.models.user import User
from backend.app.services.party_skill_boundary import PARTY_SKILL_TOOL_CONTRACTS, PARTY_SKILL_WRITE_TOOLS


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


def _user(db, student_no, role="student", party_type=None):
    user = User(
        student_no=student_no,
        name=student_no,
        password_hash="hash",
        role=role,
        status="active",
    )
    if party_type:
        user.party = {
            "party_type": party_type,
            "apply_status": "active",
            "class_name": "大数据25级",
        }
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_member_roster_is_admin_only(db):
    student = _user(db, "S-PARTY", party_type="正式党员")
    with pytest.raises(BusinessSkillPermissionError):
        asyncio.run(PartyQueryExecutor().execute("党员有多少人", student, db))

    admin = _user(db, "A-PARTY", role="admin")
    result = asyncio.run(PartyQueryExecutor().execute("党员名单", admin, db))
    assert result["read_only"] is True
    assert result["query_type"] == "member_list"
    assert result["total"] == 1
    assert result["items"][0]["user_id"] == student.id


def test_self_records_and_party_agent_tools_delegate(db):
    member = _user(db, "M-PARTY", party_type="预备党员")
    result = asyncio.run(PartyQueryExecutor().execute("我的党建活动记录", member, db))
    assert result["query_type"] == "my_records"
    assert result["read_only"] is True

    tools = AgentTools(db, member.id)
    payload = tools.get_party_my_records()
    assert "records" in payload
    assert set(PARTY_SKILL_TOOL_CONTRACTS).issubset(set(AgentTools.get_tool_list()))


def test_material_rag_filters_sensitive_sources(db, monkeypatch):
    member = _user(db, "RAG-PARTY", party_type="正式党员")
    monkeypatch.setattr(
        RAGService,
        "search",
        staticmethod(
            lambda *args, **kwargs: [
                {
                    "file_id": 1,
                    "file_name": "主题党日学习材料.pdf",
                    "chunk_content": "党章学习内容",
                    "page_no": 2,
                },
                {
                    "file_id": 2,
                    "file_name": "思想汇报.docx",
                    "chunk_content": "个人发展材料",
                    "page_no": 1,
                },
            ]
        ),
    )
    result = asyncio.run(PartyQueryExecutor().execute("查询活动学习材料内容", member, db))
    assert result["query_type"] == "materials"
    assert [item["file_name"] for item in result["citations"]] == ["主题党日学习材料.pdf"]


def test_party_skill_exposes_no_write_contracts():
    assert PARTY_SKILL_WRITE_TOOLS == ()
    assert all(contract["read_only"] for contract in PARTY_SKILL_TOOL_CONTRACTS.values())
    assert not any(name.startswith(("create_party", "update_party", "delete_party")) for name in AgentTools.get_tool_list())
