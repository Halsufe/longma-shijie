import json
from datetime import datetime

from sqlalchemy.orm import Session

from backend.app.models.skill_embedding import SkillEmbedding


class SkillEmbeddingRepository:
    @staticmethod
    def upsert(
        db: Session,
        *,
        entity_type: str,
        entity_id: int,
        source_text: str,
        embedding: list[float],
        version: int = 1,
    ) -> SkillEmbedding:
        item = db.query(SkillEmbedding).filter(
            SkillEmbedding.entity_type == entity_type,
            SkillEmbedding.entity_id == entity_id,
        ).first()
        if item is None:
            item = SkillEmbedding(entity_type=entity_type, entity_id=entity_id)
            db.add(item)
        item.source_text = source_text
        item.embedding_json = json.dumps(embedding, separators=(",", ":"))
        item.version = version
        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def list_by_type(db: Session, entity_type: str) -> list[SkillEmbedding]:
        return db.query(SkillEmbedding).filter(
            SkillEmbedding.entity_type == entity_type
        ).order_by(SkillEmbedding.entity_id).all()

    @staticmethod
    def delete_by_entity(db: Session, entity_type: str, entity_id: int) -> int:
        deleted = db.query(SkillEmbedding).filter(
            SkillEmbedding.entity_type == entity_type,
            SkillEmbedding.entity_id == entity_id,
        ).delete(synchronize_session=False)
        db.commit()
        return int(deleted)

    @staticmethod
    def list_stale(
        db: Session,
        entity_type: str,
        updated_before: datetime,
    ) -> list[SkillEmbedding]:
        return db.query(SkillEmbedding).filter(
            SkillEmbedding.entity_type == entity_type,
            SkillEmbedding.updated_at < updated_before,
        ).order_by(SkillEmbedding.updated_at).all()
