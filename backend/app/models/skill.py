from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base, local_now


class Skill(Base):
    """Skill 定义（系统内置 + 可扩展）"""
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    triggers: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON 数组字符串
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(30), default="text", nullable=False)  # text/code/utility
    model_config_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # 模型参数 JSON
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # 系统内置不可删
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: local_now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: local_now(),
        onupdate=lambda: local_now(),
        nullable=False,
    )


class SkillCall(Base):
    """Skill 调用记录"""
    __tablename__ = "skill_calls"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    skill_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    input: Mapped[str] = mapped_column(Text, nullable=False, default="")
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="success", nullable=False)  # success/failed
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_usage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: local_now(), nullable=False
    )
