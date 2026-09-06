from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.database import Base
from backend.app.core.errors import AppException
from backend.app.models.party import PoliticalLearningMaterial
from backend.app.models.user import User
from backend.app.services.party_skill_boundary import (
    PARTY_SKILL_WRITE_TOOLS,
    POLITICAL_SKILL_TOOL_CONTRACTS,
    PartySkillBoundary,
)
from backend.app.services.party_workflow_events import (
    PARTY_POLITICAL_STATUS_APPROVED,
    POLITICAL_WORKFLOW_EVENT_DEFINITIONS,
    WORKFLOW_EVENT_DEFINITIONS,
)


def test_political_skill_methods_are_read_only_and_follow_visibility() -> None:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, future=True)
    try:
        with factory() as db:
            student = User(
                student_no="league",
                name="团员",
                password_hash="x",
                role="student",
                status="active",
                political_status="共青团员",
            )
            alumni = User(
                student_no="alumni",
                name="校友",
                password_hash="x",
                role="alumni",
                status="active",
            )
            admin = User(
                student_no="admin",
                name="管理员",
                password_hash="x",
                role="admin",
                status="active",
            )
            db.add_all([student, alumni, admin])
            db.flush()
            material = PoliticalLearningMaterial(
                title="团员资料", status="published", created_by=admin.id
            )
            material.applicable_roles = ["共青团员"]
            db.add(material)
            db.commit()

            boundary = PartySkillBoundary(db, student)
            assert boundary.get_my_political_status()["political_status"] == "共青团员"
            assert boundary.list_political_learning_materials()["total"] == 1
            assert PartySkillBoundary(db, admin).get_political_status_stats()["total"] == 1
            with pytest.raises(AppException) as exc_info:
                PartySkillBoundary(db, alumni).get_my_political_status()
            assert exc_info.value.status_code == 403
    finally:
        engine.dispose()
    assert PARTY_SKILL_WRITE_TOOLS == ()
    assert set(POLITICAL_SKILL_TOOL_CONTRACTS) == {
        "get_my_political_status",
        "list_political_learning_materials",
        "get_political_status_stats",
    }
    assert all(item["read_only"] for item in POLITICAL_SKILL_TOOL_CONTRACTS.values())


def test_political_approval_event_is_available_to_workflow_consumers() -> None:
    assert POLITICAL_WORKFLOW_EVENT_DEFINITIONS[PARTY_POLITICAL_STATUS_APPROVED] == {
        "payload_fields": ("review_id", "user_id", "political_status"),
        "destination": "notification_center",
    }
    assert PARTY_POLITICAL_STATUS_APPROVED in WORKFLOW_EVENT_DEFINITIONS
