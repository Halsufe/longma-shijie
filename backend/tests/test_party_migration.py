import json
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_REVISION = "h901e2b3c4d5"
PARTY_REVISION = "i012f3c4d5e6"
HEAD_REVISION = "p7890q1r2s3"


def _alembic_config(database_url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_party_json_properties_tolerate_legacy_and_invalid_values() -> None:
    from backend.app.models.user import User

    user = User()
    assert user.party == {}

    user.party_json = ""
    assert user.party == {}
    user.party_json = "not-json"
    assert user.party == {}
    user.party_json = "[]"
    assert user.party == {}

    user.party = {"party_type": "正式党员", "branch_name": "大数据党支部"}
    assert user.party == {
        "party_type": "正式党员",
        "branch_name": "大数据党支部",
    }
    assert json.loads(user.party_json) == user.party


def test_party_activity_json_properties_tolerate_invalid_values() -> None:
    from backend.app.models.party import PartyActivity

    activity = PartyActivity(
        target_member_ids_json="invalid",
        materials_json="{}",
        summary_attachments_json=None,
    )

    assert activity.target_member_ids == []
    assert activity.materials == []
    assert activity.summary_attachments == []

    activity.target_member_ids = [1, 2]
    activity.materials = [{"name": "学习材料.pdf"}]
    activity.summary_attachments = [{"name": "总结.pdf"}]
    assert activity.target_member_ids == [1, 2]
    assert activity.materials == [{"name": "学习材料.pdf"}]
    assert activity.summary_attachments == [{"name": "总结.pdf"}]


def test_party_migration_upgrade_downgrade_preserves_legacy_users(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "party_migration.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("DB_URL", database_url)
    config = _alembic_config(database_url)

    command.upgrade(config, BASE_REVISION)
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO users (
                    id, student_no, name, password_hash, role, status,
                    created_at, updated_at
                ) VALUES (
                    1, 'legacy-party-001', '旧用户', 'hash', 'student', 'active',
                    '2026-01-01 00:00:00', '2026-01-01 00:00:00'
                )
                """
            )
        )

    command.upgrade(config, PARTY_REVISION)

    inspector = inspect(engine)
    assert {
        "party_activities",
        "party_activity_participants",
        "party_materials",
    }.issubset(inspector.get_table_names())
    user_columns = {
        column["name"]: column for column in inspector.get_columns("users")
    }
    assert user_columns["party_json"]["nullable"] is False

    activity_indexes = {
        index["name"]: index for index in inspector.get_indexes("party_activities")
    }
    assert activity_indexes["ix_party_activities_status_start_at"][
        "column_names"
    ] == ["status", "start_at"]
    assert activity_indexes["ix_party_activities_category_start_at"][
        "column_names"
    ] == ["category", "start_at"]

    participant_indexes = {
        index["name"]: index
        for index in inspector.get_indexes("party_activity_participants")
    }
    assert participant_indexes["uq_party_participant"]["unique"] == 1
    assert participant_indexes["uq_party_participant"]["column_names"] == [
        "activity_id",
        "user_id",
    ]
    participant_foreign_keys = {
        tuple(foreign_key["constrained_columns"]): foreign_key
        for foreign_key in inspector.get_foreign_keys(
            "party_activity_participants"
        )
    }
    assert participant_foreign_keys[("activity_id",)]["referred_table"] == (
        "party_activities"
    )
    assert participant_foreign_keys[("activity_id",)]["options"]["ondelete"] == (
        "CASCADE"
    )
    assert participant_foreign_keys[("user_id",)]["referred_table"] == "users"

    material_indexes = {
        index["name"]: index for index in inspector.get_indexes("party_materials")
    }
    assert material_indexes["ix_party_materials_user"]["column_names"] == [
        "user_id",
        "material_type",
    ]
    assert material_indexes["ix_party_materials_uploaded_at"][
        "column_names"
    ] == ["uploaded_at"]
    material_foreign_keys = {
        tuple(foreign_key["constrained_columns"]): foreign_key
        for foreign_key in inspector.get_foreign_keys("party_materials")
    }
    assert material_foreign_keys[("user_id",)]["referred_table"] == "users"
    assert material_foreign_keys[("uploaded_by",)]["referred_table"] == "users"

    with engine.begin() as connection:
        legacy_party_json = connection.execute(
            text("SELECT party_json FROM users WHERE id = 1")
        ).scalar_one()
        assert legacy_party_json == "{}"
        connection.execute(
            text(
                """
                INSERT INTO party_activities (
                    id, title, category, content, location, start_at, end_at,
                    target_roles, created_by, created_at, updated_at
                ) VALUES (
                    1, '主题党日', '主题党日', '学习内容', '会议室',
                    '2026-08-05 09:00:00', '2026-08-05 11:00:00',
                    'party_members', 1,
                    '2026-08-05 08:00:00', '2026-08-05 08:00:00'
                )
                """
            )
        )
        activity_defaults = connection.execute(
            text(
                """
                SELECT status, target_member_ids_json, materials_json,
                       summary_attachments_json
                FROM party_activities WHERE id = 1
                """
            )
        ).mappings().one()
        assert dict(activity_defaults) == {
            "status": "draft",
            "target_member_ids_json": "[]",
            "materials_json": "[]",
            "summary_attachments_json": "[]",
        }
        connection.execute(
            text(
                """
                INSERT INTO party_activity_participants (
                    activity_id, user_id, created_at, updated_at
                ) VALUES (
                    1, 1, '2026-08-05 08:00:00', '2026-08-05 08:00:00'
                )
                """
            )
        )

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO party_activity_participants (
                        activity_id, user_id, created_at, updated_at
                    ) VALUES (
                        1, 1, '2026-08-05 08:00:00', '2026-08-05 08:00:00'
                    )
                    """
                )
            )

    command.downgrade(config, BASE_REVISION)

    inspector = inspect(engine)
    assert "party_json" not in {
        column["name"] for column in inspector.get_columns("users")
    }
    assert not {
        "party_activities",
        "party_activity_participants",
        "party_materials",
    }.intersection(inspector.get_table_names())
    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT name FROM users WHERE id = 1")
        ).scalar_one() == "旧用户"

    command.upgrade(config, PARTY_REVISION)
    with engine.connect() as connection:
        restored = connection.execute(
            text("SELECT name, party_json FROM users WHERE id = 1")
        ).mappings().one()
        assert dict(restored) == {"name": "旧用户", "party_json": "{}"}


def test_upgrade_handles_tables_precreated_by_application_startup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.app.models.party import (
        PartyActivity,
        PartyActivityParticipant,
        PartyMaterial,
    )
    from backend.app.models.skill_embedding import SkillEmbedding

    database_path = tmp_path / "precreated_tables.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("DB_URL", database_url)
    config = _alembic_config(database_url)

    command.upgrade(config, BASE_REVISION)
    engine = create_engine(database_url)
    for table in (
        PartyActivity.__table__,
        PartyActivityParticipant.__table__,
        PartyMaterial.__table__,
        SkillEmbedding.__table__,
    ):
        table.create(engine)

    assert "party_json" not in {
        column["name"] for column in inspect(engine).get_columns("users")
    }

    command.upgrade(config, "head")

    inspector = inspect(engine)
    assert "party_json" in {
        column["name"] for column in inspector.get_columns("users")
    }
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
            HEAD_REVISION
        )
