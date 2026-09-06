from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.database import Base
from backend.app.models.user import User
from backend.app.services.party_stats_service import PartyStatsService


LEAGUE = "\u5171\u9752\u56e2\u5458"
MEMBER = "\u4e2d\u5171\u515a\u5458"
MASS = "\u7fa4\u4f17"
CLASS_A = "A\u73ed"
CLASS_B = "B\u73ed"


def test_political_stats_use_general_status_and_combined_filter() -> None:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, future=True)
    try:
        with factory() as db:
            member = User(
                student_no="member",
                name="member",
                password_hash="x",
                role="student",
                status="active",
                political_status=MEMBER,
            )
            member.party = {"class_name": CLASS_A, "grade": "25"}
            league = User(
                student_no="league",
                name="league",
                password_hash="x",
                role="student",
                status="active",
                political_status=LEAGUE,
            )
            league.party = {"class_name": CLASS_A, "grade": "25"}
            mass = User(
                student_no="mass",
                name="mass",
                password_hash="x",
                role="student",
                status="active",
                political_status=MASS,
            )
            mass.party = {"class_name": CLASS_B, "grade": "24"}
            db.add_all([member, league, mass])
            db.commit()
            stats = PartyStatsService.build(
                db,
                class_name=CLASS_A,
                grade="25",
                political_status_filter=LEAGUE,
            )
        assert stats["filters"]["political_status"] == LEAGUE
        assert stats["political_counts"] == {
            "total": 1,
            "by_status": [{"key": LEAGUE, "label": LEAGUE, "count": 1}],
            "by_class": [{"key": CLASS_A, "label": CLASS_A, "count": 1}],
            "by_grade": [{"key": "25", "label": "25", "count": 1}],
        }
    finally:
        engine.dispose()
