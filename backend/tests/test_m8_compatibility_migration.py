import json
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from backend.app.models.achievement import Achievement


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_REVISION = "g890d1a2b3c4"
DETAILS_REVISION = "h901e2b3c4d5"
DETAILS_INDEX = "ix_achievements_user_id_achievement_date"


def _alembic_config(database_url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_details_and_legacy_member_ids_properties() -> None:
    achievement = Achievement(details_json=None, member_ids_json="[12, 34]")

    assert achievement.details == {}
    assert achievement.member_ids == [12, 34]

    achievement.details = {"authors": "张三, 李四", "sci_indexed": True}
    assert achievement.details == {"authors": "张三, 李四", "sci_indexed": True}
    assert json.loads(achievement.details_json) == achievement.details
    assert achievement.member_ids_json == "[12, 34]"

    achievement.details_json = "[]"
    assert achievement.details == {}
    achievement.details_json = "not-json"
    assert achievement.details == {}


def test_migration_upgrade_downgrade_preserves_legacy_data(
    tmp_path: Path, monkeypatch
) -> None:
    database_path = tmp_path / "m8_migration.db"
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
                    1, 'legacy-001', '旧用户', 'hash', 'student', 'active',
                    '2026-01-01 00:00:00', '2026-01-01 00:00:00'
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO achievements (
                    id, user_id, category, title, description,
                    achievement_date, level, member_ids_json,
                    created_at, updated_at
                ) VALUES (
                    1, 1, 'award', '旧成果', '旧描述',
                    '2025-06', '国家级', '[1, 2]',
                    '2026-01-01 00:00:00', '2026-01-01 00:00:00'
                )
                """
            )
        )

    command.upgrade(config, DETAILS_REVISION)

    inspector = inspect(engine)
    columns = {column["name"]: column for column in inspector.get_columns("achievements")}
    indexes = {index["name"]: index for index in inspector.get_indexes("achievements")}
    assert columns["details_json"]["nullable"] is False
    assert DETAILS_INDEX in indexes
    assert indexes[DETAILS_INDEX]["column_names"] == ["user_id", "achievement_date"]

    with engine.begin() as connection:
        legacy = connection.execute(
            text(
                """
                SELECT title, description, achievement_date, level,
                       member_ids_json, details_json
                FROM achievements WHERE id = 1
                """
            )
        ).mappings().one()
        assert dict(legacy) == {
            "title": "旧成果",
            "description": "旧描述",
            "achievement_date": "2025-06",
            "level": "国家级",
            "member_ids_json": "[1, 2]",
            "details_json": "{}",
        }
        connection.execute(
            text("UPDATE achievements SET details_json = :details WHERE id = 1"),
            {"details": '{"award_grade":"一等奖"}'},
        )

    command.downgrade(config, BASE_REVISION)

    inspector = inspect(engine)
    assert "details_json" not in {
        column["name"] for column in inspector.get_columns("achievements")
    }
    assert DETAILS_INDEX not in {
        index["name"] for index in inspector.get_indexes("achievements")
    }
    with engine.connect() as connection:
        legacy = connection.execute(
            text(
                """
                SELECT title, description, achievement_date, level, member_ids_json
                FROM achievements WHERE id = 1
                """
            )
        ).mappings().one()
        assert dict(legacy) == {
            "title": "旧成果",
            "description": "旧描述",
            "achievement_date": "2025-06",
            "level": "国家级",
            "member_ids_json": "[1, 2]",
        }

    command.upgrade(config, DETAILS_REVISION)
    with engine.connect() as connection:
        restored = connection.execute(
            text(
                "SELECT member_ids_json, details_json FROM achievements WHERE id = 1"
            )
        ).mappings().one()
        assert dict(restored) == {
            "member_ids_json": "[1, 2]",
            "details_json": "{}",
        }
