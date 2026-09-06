from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base, local_now


class AuditLog(Base):
    """审计日志（仅记录写操作，不存密码/Token/Key）"""
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    operator_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)  # 系统操作时为空
    operator_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # create/update/delete/login/logout
    target_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # user/course/assignment...
    target_id: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 字符串以兼容 UUID 等
    result: Mapped[str] = mapped_column(String(20), default="success", nullable=False)  # success/failed
    ip: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)  # 变更字段 JSON（脱敏）
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: local_now(), nullable=False, index=True
    )
