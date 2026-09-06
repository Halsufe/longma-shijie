import json
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base, local_now


class SkillEmbedding(Base):
    __tablename__ = "skill_embeddings"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", name="uq_skill_embedding_entity"),
        Index("ix_skill_embeddings_type_updated", "entity_type", "updated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_json: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=local_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=local_now, onupdate=local_now
    )

    @property
    def embedding(self) -> list[float]:
        try:
            value = json.loads(self.embedding_json)
        except (TypeError, json.JSONDecodeError):
            return []
        return [float(item) for item in value] if isinstance(value, list) else []
