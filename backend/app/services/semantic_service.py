from __future__ import annotations

import json
import logging
import math
import re
from collections.abc import Callable, Iterable, Sequence
from typing import Any, TypeGuard

from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.repositories.skill_embedding_repo import SkillEmbeddingRepository


logger = logging.getLogger(__name__)


class SemanticService:
    _model: Any = None
    _model_failed = False

    @classmethod
    def reset_model(cls) -> None:
        cls._model = None
        cls._model_failed = False

    @classmethod
    def _get_model(cls) -> Any | None:
        if cls._model_failed:
            return None
        if cls._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                cls._model = SentenceTransformer(
                    settings.EMBEDDING_MODEL_NAME,
                    device=settings.EMBEDDING_DEVICE,
                    local_files_only=True,
                )
            except Exception as exc:
                cls._model_failed = True
                logger.warning("Embedding model unavailable; semantic Skills will use fallback: %s", exc)
                return None
        return cls._model

    @staticmethod
    def _is_vector(value: object) -> TypeGuard[list[float]]:
        return isinstance(value, list) and bool(value) and all(
            isinstance(item, (int, float)) for item in value
        )

    @staticmethod
    def normalize(vector: Sequence[float]) -> list[float]:
        norm = math.sqrt(sum(float(value) ** 2 for value in vector))
        if norm == 0:
            return [0.0 for _ in vector]
        return [float(value) / norm for value in vector]

    @classmethod
    def embed(cls, texts: str | Sequence[str]) -> list[float] | list[list[float]] | None:
        single = isinstance(texts, str)
        values = [texts] if single else list(texts)
        if not values:
            return []
        model = cls._get_model()
        if model is None:
            return None
        try:
            encoded = model.encode(
                values,
                batch_size=settings.EMBEDDING_BATCH_SIZE,
                normalize_embeddings=True,
            )
            vectors = [cls.normalize(row.tolist() if hasattr(row, "tolist") else row) for row in encoded]
            return vectors[0] if single else vectors
        except Exception as exc:
            logger.warning("Embedding generation failed; using fallback: %s", exc)
            return None

    @staticmethod
    def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
        if not left or len(left) != len(right):
            return 0.0
        left_norm = SemanticService.normalize(left)
        right_norm = SemanticService.normalize(right)
        return max(-1.0, min(1.0, sum(a * b for a, b in zip(left_norm, right_norm))))

    @staticmethod
    def keyword_score(query: str, candidate: str) -> float:
        tokens = {token.lower() for token in re.findall(r"[\w\u4e00-\u9fff]+", query) if token}
        if not tokens:
            return 0.0
        candidate_lower = candidate.lower()
        hits = sum(1 for token in tokens if token in candidate_lower)
        return hits / len(tokens)

    @classmethod
    def search(
        cls,
        db: Session,
        *,
        entity_type: str,
        query_text: str,
        popularity: dict[int, float] | None = None,
        allowed_entity_ids: set[int] | None = None,
        limit: int | None = None,
        fallback: Callable[[], list[dict[str, Any]]] | None = None,
    ) -> list[dict[str, Any]]:
        query_vector = cls.embed(query_text)
        if not cls._is_vector(query_vector):
            return fallback() if fallback else []

        results: list[dict[str, Any]] = []
        for item in SkillEmbeddingRepository.list_by_type(db, entity_type):
            if allowed_entity_ids is not None and item.entity_id not in allowed_entity_ids:
                continue
            try:
                vector = json.loads(item.embedding_json)
            except (TypeError, json.JSONDecodeError):
                continue
            cosine = cls.cosine_similarity(query_vector, vector)
            keyword = cls.keyword_score(query_text, item.source_text)
            popularity_score = max(0.0, min(1.0, (popularity or {}).get(item.entity_id, 0.0)))
            score = 0.7 * cosine + 0.2 * keyword + 0.1 * popularity_score
            if score >= settings.SEMANTIC_MIN_SCORE:
                results.append({"entity_id": item.entity_id, "score": round(score, 6)})
        results.sort(key=lambda result: result["score"], reverse=True)
        if not results:
            return fallback() if fallback else []
        return results[: max(1, min(limit or settings.SKILL_RECOMMEND_LIMIT, 10))]

    @classmethod
    def refresh(
        cls,
        db: Session,
        *,
        entity_type: str,
        entity_id: int,
        source_text: str,
        version: int = 1,
    ) -> bool:
        vector = cls.embed(source_text)
        if not cls._is_vector(vector):
            return False
        SkillEmbeddingRepository.upsert(
            db,
            entity_type=entity_type,
            entity_id=entity_id,
            source_text=source_text,
            embedding=[float(value) for value in vector],
            version=version,
        )
        return True

    @classmethod
    def refresh_resource(cls, db: Session, resource: Any) -> bool:
        if resource.type != "competition" or resource.status != "approved" or resource.deleted_at is not None:
            SkillEmbeddingRepository.delete_by_entity(db, "competition", resource.id)
            return False
        text = " ".join(
            part for part in [resource.title, resource.content, " ".join(resource.tags), resource.source] if part
        )
        return cls.refresh(db, entity_type="competition", entity_id=resource.id, source_text=text)

    @classmethod
    def refresh_teacher_direction(cls, db: Session, direction: Any) -> bool:
        if not direction.is_active or direction.deleted_at is not None:
            SkillEmbeddingRepository.delete_by_entity(db, "teacher_direction", direction.id)
            return False
        text = " ".join(
            part for part in [direction.title, direction.description, " ".join(direction.tags)] if part
        )
        return cls.refresh(db, entity_type="teacher_direction", entity_id=direction.id, source_text=text)

    @classmethod
    def refresh_teacher_profile(cls, db: Session, user: Any) -> bool:
        if user.role != "teacher" or user.deleted_at is not None:
            SkillEmbeddingRepository.delete_by_entity(db, "teacher_profile", user.id)
            return False
        profile = user.profile if isinstance(user.profile, dict) else {}
        values: list[str] = [user.name]
        for key in ("research", "skills", "directions", "field"):
            value = profile.get(key)
            if isinstance(value, str):
                values.append(value)
            elif isinstance(value, Iterable):
                values.extend(str(item) for item in value)
        return cls.refresh(
            db,
            entity_type="teacher_profile",
            entity_id=user.id,
            source_text=" ".join(filter(None, values)),
        )
