from __future__ import annotations

from datetime import timedelta
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.datastructures import Headers

from backend.app.ai.retriever import RAGService
from backend.app.core.config import settings
from backend.app.core.database import Base, local_now
from backend.app.core.errors import AppException
from backend.app.core.storage import StorageService
from backend.app.models.file import FileChunk, KnowledgeFile
from backend.app.models.notification import Notification
from backend.app.models.party import PartyActivity
from backend.app.models.user import User
from backend.app.services.party_activity_service import PartyActivityService
from backend.app.services.party_knowledge_adapter import PartyKnowledgeAdapter
from backend.app.services.party_notify_adapter import PartyNotifyAdapter
from backend.app.services.party_profile_service import PartyProfileService
from backend.app.services.party_registration_service import PartyRegistrationService
from backend.app.services.party_skill_boundary import (
    PARTY_SKILL_TOOL_CONTRACTS,
    PARTY_SKILL_WRITE_TOOLS,
    PartySkillBoundary,
)
from backend.app.services.party_workflow_events import (
    PARTY_ACTIVITY_FINISHED,
    PARTY_ACTIVITY_PUBLISHED,
    PARTY_ACTIVITY_STARTING,
    PARTY_REGISTRATION_DEADLINE_APPROACHING,
    PARTY_STATUS_CHANGED,
    PARTY_WORKFLOW_EVENT_DEFINITIONS,
    PARTY_WORKFLOW_EVENTS,
)


def _profile() -> dict:
    return {
        "party_type": "入党积极分子",
        "branch_name": "大数据党支部",
        "class_name": "大数据25级",
        "grade": "25",
        "apply_date": "2025-01",
        "activist_date": None,
        "target_date": None,
        "probation_date": None,
        "full_date": None,
        "party_join_date": None,
        "apply_status": "递交申请",
        "stop_reason": None,
        "introducer_names": None,
        "mentor_names": None,
        "remark": None,
    }


@pytest.fixture()
def dependency_db(tmp_path: Path):
    previous_storage = settings.STORAGE_PATH
    settings.STORAGE_PATH = str(tmp_path / "storage")
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    factory = sessionmaker(bind=engine, autoflush=False, future=True)
    Base.metadata.create_all(engine)
    db = factory()
    admin = User(
        student_no="admin-m7",
        name="管理员",
        password_hash="unused",
        role="admin",
        status="active",
    )
    member = User(
        student_no="member-m7",
        name="党建成员",
        password_hash="unused",
        role="student",
        status="active",
    )
    member.party = _profile()
    plain = User(
        student_no="plain-m7",
        name="普通学生",
        password_hash="unused",
        role="student",
        status="active",
    )
    other = User(
        student_no="other-m7",
        name="其他学生",
        password_hash="unused",
        role="student",
        status="active",
    )
    db.add_all([admin, member, plain, other])
    db.commit()
    for user in (admin, member, plain, other):
        db.refresh(user)
    try:
        yield db, admin, member, plain, other
    finally:
        db.close()
        engine.dispose()
        settings.STORAGE_PATH = previous_storage


def _activity(db, admin: User, *, status: str = "draft") -> PartyActivity:
    now = local_now()
    activity = PartyActivity(
        title="M7 党建学习活动",
        category="理论学习",
        content="学习党章和支部工作要求。",
        location="A101",
        start_at=now + timedelta(days=3),
        end_at=now + timedelta(days=3, hours=2),
        registration_deadline=now + timedelta(days=2),
        target_roles="全体学生",
        max_participants=20,
        status=status,
        created_by=admin.id,
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


def _upload(name: str, content_type: str, data: bytes) -> UploadFile:
    return UploadFile(
        file=BytesIO(data),
        filename=name,
        headers=Headers({"content-type": content_type}),
    )


def test_notification_adapter_is_idempotent_and_integrated(dependency_db) -> None:
    db, admin, member, plain, other = dependency_db
    activity = _activity(db, admin)
    published = PartyActivityService.transition(db, activity.id, "published")
    notices = (
        db.query(Notification)
        .filter(
            Notification.type == "party_activity_notice",
            Notification.ref_type == "party_activity",
            Notification.ref_id == activity.id,
        )
        .all()
    )
    assert {notice.user_id for notice in notices} == {
        member.id,
        plain.id,
        other.id,
    }
    assert PartyNotifyAdapter.notify_party_activity_published(
        db, activity=published, target_user_ids=[member.id, plain.id]
    ) == 0
    assert db.query(Notification).filter(
        Notification.ref_type == "party_activity",
        Notification.ref_id == activity.id,
    ).count() == 3

    participant = PartyRegistrationService.register(db, activity.id, member)
    registration_notice = db.query(Notification).filter(
        Notification.user_id == member.id,
        Notification.ref_type == "party_registration_registered",
        Notification.ref_id == participant.id,
    ).one()
    assert registration_notice.type == "party_activity_notice"

    with patch(
        "backend.app.services.party_registration_service.local_now",
        return_value=published.start_at,
    ):
        PartyRegistrationService.sign_in(db, activity.id, member)
    assert db.query(Notification).filter(
        Notification.user_id == member.id,
        Notification.ref_type == "party_attendance_signed_in",
        Notification.ref_id == participant.id,
    ).count() == 1

    changed = PartyProfileService.change_status(
        db,
        member.id,
        {"apply_status": "确定为积极分子", "effective_date": "2025-02"},
        admin,
    )
    assert changed.party["apply_status"] == "确定为积极分子"
    assert db.query(Notification).filter(
        Notification.type == "party_status_change",
        Notification.ref_type == "party_member",
        Notification.ref_id == member.id,
    ).count() == 1

    assert PartyNotifyAdapter.notify_party_activity_reminder(
        db,
        activity_id=activity.id,
        activity_title=activity.title,
        target_user_ids=[member.id],
        content="活动即将开始。",
    ) == 1
    assert PartyNotifyAdapter.notify_party_activity_reminder(
        db,
        activity_id=activity.id,
        activity_title=activity.title,
        target_user_ids=[member.id],
        content="活动即将开始。",
    ) == 0


def test_learning_material_enters_class_rag_and_development_material_is_excluded(
    dependency_db,
) -> None:
    db, admin, member, _, _ = dependency_db
    activity = _activity(db, admin)
    stored_name, _ = StorageService.save_bytes(
        "party_activities",
        activity.id,
        "党章学习重点与支部工作要求".encode("utf-8"),
        ".txt",
    )
    knowledge = PartyKnowledgeAdapter.ingest_activity_material(
        db,
        activity=activity,
        attachment={
            "original_name": "党章学习重点.txt",
            "stored_name": stored_name,
            "mime_type": "text/plain",
        },
    )
    assert knowledge is not None
    assert knowledge.scope == "class"
    assert knowledge.parse_status == "ready"
    assert db.query(FileChunk).filter(FileChunk.file_id == knowledge.id).count() == 1
    assert PartyKnowledgeAdapter.ingest_activity_material(
        db,
        activity=activity,
        attachment={
            "original_name": "党章学习重点.txt",
            "stored_name": stored_name,
            "mime_type": "text/plain",
        },
    ).id == knowledge.id
    results = RAGService.search(
        db, query="党章学习", user_id=member.id, scope="class", limit=5
    )
    assert any(item["file_id"] == knowledge.id for item in results)

    PartyActivityService.upload_material(
        db,
        activity.id,
        _upload("活动照片.png", "image/png", b"image-content"),
    )
    image_knowledge = db.query(KnowledgeFile).filter(
        KnowledgeFile.scope == "class",
        KnowledgeFile.original_name == "活动照片.png",
    ).one()
    assert image_knowledge.parse_status == "failed"

    before = db.query(KnowledgeFile).count()
    material = PartyProfileService.upload_material(
        db,
        user_id=member.id,
        material_type="思想汇报",
        title="个人思想汇报",
        file=_upload("思想汇报.png", "image/png", b"sensitive-image"),
        uploaded_by=admin.id,
    )
    assert material.id
    assert PartyKnowledgeAdapter.ingest_development_material(material) is None
    assert db.query(KnowledgeFile).count() == before


def test_skill_boundary_contracts_and_permissions_are_read_only(dependency_db) -> None:
    db, admin, member, plain, other = dependency_db
    activity = _activity(db, admin, status="published")
    assert set(PARTY_SKILL_TOOL_CONTRACTS) == {
        "list_party_members",
        "get_party_member",
        "list_party_activities",
        "get_party_activity",
        "get_party_my_records",
    }
    assert all(item["read_only"] for item in PARTY_SKILL_TOOL_CONTRACTS.values())
    assert PARTY_SKILL_WRITE_TOOLS == ()

    admin_tools = PartySkillBoundary(db, admin)
    assert admin_tools.list_party_members()["total"] == 1
    assert admin_tools.get_party_member(member.id)["user_id"] == member.id

    member_tools = PartySkillBoundary(db, member)
    assert member_tools.get_party_member(member.id)["user_id"] == member.id
    assert member_tools.list_party_activities()["items"][0]["id"] == activity.id
    assert member_tools.get_party_activity(activity.id)["id"] == activity.id
    assert member_tools.get_party_my_records()["party"]["party_type"] == "入党积极分子"

    for operation in (
        lambda: member_tools.list_party_members(),
        lambda: member_tools.get_party_member(other.id),
        lambda: PartySkillBoundary(db, plain).get_party_member(member.id),
    ):
        with pytest.raises(AppException) as exc_info:
            operation()
        assert exc_info.value.status_code == 403


def test_workflow_event_contract_has_exact_five_events_and_payloads() -> None:
    assert PARTY_WORKFLOW_EVENTS == (
        PARTY_ACTIVITY_PUBLISHED,
        PARTY_REGISTRATION_DEADLINE_APPROACHING,
        PARTY_ACTIVITY_STARTING,
        PARTY_ACTIVITY_FINISHED,
        PARTY_STATUS_CHANGED,
    )
    assert len(PARTY_WORKFLOW_EVENT_DEFINITIONS) == 5
    assert PARTY_WORKFLOW_EVENT_DEFINITIONS[PARTY_ACTIVITY_PUBLISHED][
        "payload_fields"
    ] == ("activity_id", "target_user_ids")
    assert PARTY_WORKFLOW_EVENT_DEFINITIONS[
        PARTY_REGISTRATION_DEADLINE_APPROACHING
    ]["payload_fields"] == ("activity_id", "registered_user_ids")
    assert PARTY_WORKFLOW_EVENT_DEFINITIONS[PARTY_ACTIVITY_STARTING][
        "payload_fields"
    ] == ("activity_id", "registered_user_ids")
    assert PARTY_WORKFLOW_EVENT_DEFINITIONS[PARTY_ACTIVITY_FINISHED][
        "payload_fields"
    ] == ("activity_id",)
    assert PARTY_WORKFLOW_EVENT_DEFINITIONS[PARTY_STATUS_CHANGED][
        "payload_fields"
    ] == ("user_id", "from_status", "to_status")
