from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.database import Base, local_now
from backend.app.models.party import (
    PartyActivity,
    PartyActivityParticipant,
    PartyMaterial,
    PoliticalLearningMaterial,
)
from backend.app.models.user import User
from backend.app.services.party_stats_service import PartyStatsService


def _profile(kind: str, class_name: str, grade: str, **extra) -> dict:
    value = {
        "party_type": kind,
        "class_name": class_name,
        "grade": grade,
        "branch_name": "大数据党支部",
        "apply_date": "2024-01",
        "apply_status": "递交申请",
    }
    value.update(extra)
    return value


@pytest.fixture()
def stats_db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, future=True)
    with session_factory() as db:
        users = [
            User(student_no="f", name="正式", password_hash="x", role="student", status="active"),
            User(student_no="p", name="预备", password_hash="x", role="student", status="active"),
            User(student_no="a", name="积极", password_hash="x", role="student", status="active"),
            User(student_no="n", name="普通", password_hash="x", role="student", status="active"),
            User(student_no="admin", name="管理", password_hash="x", role="admin", status="active"),
        ]
        users[0].party = _profile("正式党员", "A班", "25", apply_status="转为正式党员", full_date=f"{local_now().year}-05")
        users[1].party = _profile("预备党员", "A班", "25", apply_status="接受为预备党员")
        users[2].party = _profile("入党积极分子", "B班", "24", apply_status="确定为积极分子")
        db.add_all(users)
        db.commit()
        now = local_now()
        theme = PartyActivity(
            title="主题活动",
            category="主题党日",
            content="主题",
            location="A1",
            start_at=now - timedelta(days=2),
            end_at=now - timedelta(days=2, hours=-1),
            target_roles="全体党员",
            status="finished",
            created_by=users[4].id,
        )
        theme.materials = [
            {"name": "一.pdf", "uploaded_at": now.isoformat()},
            {"name": "二.png", "uploaded_at": now.isoformat()},
        ]
        public = PartyActivity(
            title="志愿活动",
            category="志愿公益",
            content="志愿",
            location="A2",
            start_at=now - timedelta(days=1),
            end_at=now - timedelta(days=1, hours=-1),
            target_roles="全体学生",
            status="archived",
            created_by=users[4].id,
        )
        public.materials = [{"name": "照片.jpg", "uploaded_at": now.isoformat()}]
        db.add_all([theme, public])
        db.flush()
        db.add_all(
            [
                PartyActivityParticipant(
                    activity_id=theme.id,
                    user_id=users[0].id,
                    registration_status="registered",
                    attendance_status="signed_in",
                    sign_in_method="self",
                    sign_in_time=theme.start_at,
                ),
                PartyActivityParticipant(
                    activity_id=theme.id,
                    user_id=users[1].id,
                    registration_status="registered",
                    attendance_status="absent",
                ),
                PartyMaterial(
                    user_id=users[0].id,
                    material_type="思想汇报",
                    title="A材料",
                    original_name="a.pdf",
                    stored_name="a.pdf",
                    mime_type="application/pdf",
                    size=10,
                    uploaded_by=users[4].id,
                    uploaded_at=now,
                ),
                PartyMaterial(
                    user_id=users[2].id,
                    material_type="思想汇报",
                    title="B材料",
                    original_name="b.pdf",
                    stored_name="b.pdf",
                    mime_type="application/pdf",
                    size=10,
                    uploaded_by=users[4].id,
                    uploaded_at=now,
                ),
            ]
        )
        db.commit()
    try:
        yield session_factory
    finally:
        engine.dispose()


def _counts(items) -> dict[str, int]:
    return {item["key"]: item["count"] for item in items}


def test_member_distribution_development_and_material_counts(stats_db) -> None:
    with stats_db() as db:
        stats = PartyStatsService.build(db, year=local_now().year)
    assert stats["member_counts"]["total"] == 3
    assert _counts(stats["member_counts"]["by_party_type"]) == {
        "正式党员": 1,
        "预备党员": 1,
        "入党积极分子": 1,
    }
    assert _counts(stats["member_counts"]["by_class"]) == {"A班": 2, "B班": 1}
    assert stats["development"]["annual_full_count"] == 1
    assert stats["materials"]["activity_materials"] == 3
    assert stats["materials"]["member_materials"] == 2
    assert stats["materials"]["total"] == 5


def test_participation_denominator_rates_filters_and_pagination(stats_db) -> None:
    with stats_db() as db:
        all_stats = PartyStatsService.build(db, page=1, page_size=1)
        theme = PartyStatsService.build(db, category="主题党日")
        class_a = PartyStatsService.build(db, class_name="A班", year=local_now().year)
    participation = all_stats["participation"]
    assert participation["expected_count"] == 6
    assert participation["registered_count"] == 2
    assert participation["signed_in_count"] == 1
    assert participation["participation_rate"] == pytest.approx(1 / 6, abs=0.0001)
    assert participation["registration_rate"] == pytest.approx(2 / 6, abs=0.0001)
    assert participation["total"] == 2
    assert len(participation["activities"]) == 1
    assert theme["participation"]["expected_count"] == 2
    assert theme["participation"]["participation_rate"] == 0.5
    assert class_a["member_counts"]["total"] == 2
    assert class_a["materials"]["member_materials"] == 1


def test_zero_denominator_is_zero_percent(stats_db) -> None:
    with stats_db() as db:
        stats = PartyStatsService.build(db, class_name="不存在班级")
    assert stats["member_counts"]["total"] == 0
    assert stats["participation"]["expected_count"] == 0
    assert stats["participation"]["participation_rate"] == 0.0
    assert stats["participation"]["registration_rate"] == 0.0


def test_political_counts_league_participation_and_material_metrics(stats_db) -> None:
    with stats_db() as db:
        users = db.query(User).filter(User.role == "student").order_by(User.id).all()
        users[0].political_status = "中共党员"
        users[1].political_status = "预备党员"
        users[2].political_status = "共青团员"
        users[3].political_status = "群众"
        now = local_now()
        league = PartyActivity(
            title="主题团日",
            category="主题团日",
            content="团学活动",
            location="A3",
            start_at=now,
            end_at=now + timedelta(hours=1),
            target_roles="全体团员",
            status="finished",
            created_by=users[0].id,
        )
        material = PoliticalLearningMaterial(
            title="团员资料",
            status="published",
            created_by=users[0].id,
        )
        material.applicable_roles = ["共青团员"]
        db.add_all([league, material])
        db.flush()
        db.add(
            PartyActivityParticipant(
                activity_id=league.id,
                user_id=users[2].id,
                registration_status="registered",
                attendance_status="signed_in",
            )
        )
        db.commit()
        stats = PartyStatsService.build(
            db, political_status_filter="共青团员", year=now.year
        )
    assert _counts(stats["political_counts"]["by_status"]) == {"共青团员": 1}
    assert stats["league_participation"]["expected_count"] == 1
    assert stats["league_participation"]["signed_in_count"] == 1
    assert stats["league_participation"]["participation_rate"] == 1.0
    assert stats["political_materials"]["total"] == 1
