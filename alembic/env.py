import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

from backend.app.core.config import settings
from backend.app.core.database import Base

# 导入全部模型，确保 autogenerate 能识别所有表
from backend.app.models.user import User  # noqa: F401
from backend.app.models.user_session import UserSession  # noqa: F401
from backend.app.models.chat import ChatSession, ChatMessage, ChatMessageAttachment, ChatMessageCitation  # noqa: F401
from backend.app.models.chat_request import ChatRequest  # noqa: F401
from backend.app.models.token_quota import (  # noqa: F401
    TokenQuotaPolicy, UserTokenQuotaOverride, UserDailyTokenUsage,
    ChatTokenUsageEvent, TokenQuotaAuditLog,
)
from backend.app.models.file import KnowledgeFile, FileChunk, KnowledgeFolder, KnowledgeFileVersion  # noqa: F401
from backend.app.models.runtime_config import RuntimeConfig  # noqa: F401
from backend.app.models.school import (  # noqa: F401
    Course, CourseSchedule, Assignment, Submission, SubmissionVersion, AssignmentAttachment, SubmissionAttachment,
)
from backend.app.models.notification import Notification  # noqa: F401
from backend.app.models.mentor_selection import (  # noqa: F401
    MentorSelectionBatch, MentorSelectionBatchStudent, MentorSelectionBatchMentor,
    MentorPreferenceSubmission, MentorPreferenceItem, MentorDecisionSubmission,
    MentorDecisionItem, MentorMatchResultVersion, MentorMatchResultItem,
    MentorSelectionTaskRun, MentorSelectionNotificationDelivery,
)
from backend.app.models.skill import Skill, SkillCall  # noqa: F401
from backend.app.models.audit import AuditLog  # noqa: F401
from backend.app.models.party import (  # noqa: F401
    PartyActivity,
    PartyActivityParticipant,
    PartyMaterial,
    PoliticalStatusReview,
    PoliticalLearningMaterial,
)
from backend.app.models.announcement import (  # noqa: F401
    AnnouncementSource, SchoolAnnouncement, AnnouncementOrigin, AnnouncementAttachment,
    AnnouncementTaskRun, AnnouncementDigest, AnnouncementDigestDelivery,
)
from backend.app.models.announcement import (  # noqa: F401
    AnnouncementSource, SchoolAnnouncement, AnnouncementOrigin, AnnouncementAttachment,
    AnnouncementTaskRun, AnnouncementDigest, AnnouncementDigestDelivery,
)

config = context.config

# 与应用共用同一配置源；测试仍可通过环境变量覆盖。
config.set_main_option("sqlalchemy.url", os.getenv("DB_URL", settings.DB_URL))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, render_as_batch=True
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
