"""Competition recommendation business Skill."""

import json
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from backend.app.ai.business_skills.base import BusinessSkillExecutor
from backend.app.models.user import User
from backend.app.models.resource import Resource
from backend.app.services.semantic_service import SemanticService
from backend.app.core.config import settings


class CompetitionRecommendExecutor(BusinessSkillExecutor):
    skill_name = "competition_recommend"

    async def execute(self, user_input: str, user: User, db: Session) -> dict[str, Any]:
        query = self.normalize_input(user_input)
        limit = self._parse_limit(query)
        profile_text = self._profile_text(user)
        search_text = " ".join(part for part in (profile_text, query) if part)
        try:
            candidates = db.query(Resource).filter(
                Resource.type == "competition",
                Resource.status == "approved",
                Resource.deleted_at.is_(None),
            ).all()
        except OperationalError as exc:
            if "no such table" not in str(exc).lower():
                raise
            candidates = []
        source = self._parse_option(query, "source")
        tags = self._parse_tags(query)
        candidates = [
            item for item in candidates
            if not self._is_expired(item.deadline)
            and (not source or (item.source or "").lower() == source.lower())
            and (not tags or any(tag.lower() in {value.lower() for value in item.tags} for tag in tags))
        ]
        if not candidates:
            return {
                "intent": "recommend",
                "query": query,
                "limit": limit,
                "items": [],
                "total": 0,
                "message": "暂未找到符合条件且未截止的比赛。",
            }
        candidate_map = {item.id: item for item in candidates}
        max_heat = max(1, max((item.view_count + item.like_count * 10 for item in candidates), default=0))
        popularity = {
            item.id: (item.view_count + item.like_count * 10) / max_heat for item in candidates
        }

        def fallback() -> list[dict[str, Any]]:
            ordered = sorted(
                candidates,
                key=lambda item: (item.view_count + item.like_count * 10, item.id),
                reverse=True,
            )
            return [{"entity_id": item.id, "score": round(popularity[item.id] * 0.1, 6)} for item in ordered[:limit]]

        ranked = SemanticService.search(
            db,
            entity_type="competition",
            query_text=search_text,
            popularity=popularity,
            allowed_entity_ids=set(candidate_map),
            limit=limit,
            fallback=fallback,
        )
        items = [
            self._serialize(candidate_map[result["entity_id"]], search_text, float(result["score"]))
            for result in ranked
            if result["entity_id"] in candidate_map
        ]
        return {
            "intent": "recommend",
            "query": query,
            "limit": limit,
            "items": items,
            "total": len(items),
            "message": "已结合你的画像和补充条件生成竞赛推荐。" if items else "暂未找到符合条件且未截止的比赛。",
        }

    @staticmethod
    def _parse_limit(user_input: str) -> int:
        match = re.search(r"(?:limit\s*[=:]?|前)\s*(\d+)", user_input, re.IGNORECASE)
        if match is None:
            return settings.SKILL_RECOMMEND_LIMIT
        return max(1, min(int(match.group(1)), 10))

    @staticmethod
    def _profile_text(user: User) -> str:
        profile = user.profile if isinstance(user.profile, dict) else {}
        values: list[str] = []
        for key in ("major", "research", "skills", "field", "directions", "grade"):
            value = profile.get(key)
            if isinstance(value, str) and value.strip():
                values.append(value.strip())
            elif isinstance(value, list):
                values.extend(str(item).strip() for item in value if str(item).strip())
        return " ".join(values)

    @staticmethod
    def _parse_option(query: str, name: str) -> str | None:
        match = re.search(rf"{name}\s*[=:：]\s*([^,，\s]+)", query, re.IGNORECASE)
        return match.group(1).strip() if match else None

    @staticmethod
    def _parse_tags(query: str) -> list[str]:
        match = re.search(r"tags?\s*[=:：]\s*([^\s]+)", query, re.IGNORECASE)
        return re.split(r"[,，]", match.group(1)) if match else []

    @staticmethod
    def _is_expired(deadline: datetime | None) -> bool:
        if deadline is None:
            return False
        current = datetime.now(timezone.utc)
        normalized = deadline if deadline.tzinfo else deadline.replace(tzinfo=timezone.utc)
        return normalized < current

    @staticmethod
    def _serialize(resource: Resource, query_text: str, score: float) -> dict[str, Any]:
        matched_tags = [tag for tag in resource.tags if tag.lower() in query_text.lower()]
        reason_bits = []
        if matched_tags:
            reason_bits.append(f"与你的方向或技能“{'、'.join(matched_tags[:3])}”匹配")
        else:
            reason_bits.append("综合比赛内容与你的需求和画像进行匹配")
        if resource.deadline:
            reason_bits.append(f"截止 {resource.deadline.date().isoformat()}")
        if resource.source:
            reason_bits.append(f"来源：{resource.source}")
        return {
            "id": resource.id,
            "title": resource.title,
            "type": resource.type,
            "tags": resource.tags,
            "source": resource.source,
            "deadline": resource.deadline.isoformat() if resource.deadline else None,
            "view_count": resource.view_count,
            "like_count": resource.like_count,
            "reason": "推荐理由：" + "；".join(reason_bits),
            "score": round(score, 6),
        }
