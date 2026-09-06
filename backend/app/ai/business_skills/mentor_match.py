"""Mentor matching business Skill."""

import re
from typing import Any

from sqlalchemy.orm import Session

from backend.app.ai.business_skills.base import BusinessSkillExecutor
from backend.app.models.user import User
from backend.app.models.teacher import TeacherDirection
from backend.app.services.semantic_service import SemanticService
from backend.app.core.config import settings


class MentorMatchExecutor(BusinessSkillExecutor):
    skill_name = "mentor_match"

    async def execute(self, user_input: str, user: User, db: Session) -> dict[str, Any]:
        project_description = self.normalize_input(user_input)
        needs_more_input = len(project_description) < 20
        if needs_more_input:
            return {
                "intent": "match",
                "project_description": project_description,
                "needs_more_input": True,
                "items": [],
                "total": 0,
                "message": "请补充项目目标、技术路线或研究关键词（至少 20 个字符）后再匹配导师。",
            }

        limit = self._parse_limit(project_description)
        teacher_name = self._parse_option(project_description, "teacher_name")
        tag = self._parse_option(project_description, "tag")
        query = db.query(TeacherDirection, User).join(User, User.id == TeacherDirection.teacher_id).filter(
            TeacherDirection.deleted_at.is_(None),
            TeacherDirection.is_active.is_(True),
            User.role == "teacher",
            User.status == "active",
            User.deleted_at.is_(None),
        )
        if teacher_name:
            query = query.filter(User.name.ilike(f"%{teacher_name}%"))
        rows: list[tuple[TeacherDirection, User]] = [
            (row[0], row[1]) for row in query.all()
        ]
        if tag:
            rows = [(direction, teacher) for direction, teacher in rows if tag.lower() in {
                value.lower() for value in direction.tags
            }]
        direction_map = {direction.id: (direction, teacher) for direction, teacher in rows}

        def fallback() -> list[dict[str, Any]]:
            scored: list[tuple[float, int]] = []
            for direction, _teacher in rows:
                text = " ".join([direction.title, direction.description or "", " ".join(direction.tags)])
                score = SemanticService.keyword_score(project_description, text)
                scored.append((score, direction.id))
            scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
            return [{"entity_id": direction_id, "score": score} for score, direction_id in scored[: limit * 3]]

        ranked = SemanticService.search(
            db,
            entity_type="teacher_direction",
            query_text=project_description,
            allowed_entity_ids=set(direction_map),
            limit=min(limit * 3, 10),
            fallback=fallback,
        )
        best_by_teacher: dict[int, dict[str, Any]] = {}
        for result in ranked:
            row = direction_map.get(result["entity_id"])
            if row is None:
                continue
            direction, teacher = row
            item = self._serialize(teacher, direction, project_description, float(result["score"]))
            existing = best_by_teacher.get(teacher.id)
            if existing is None or item["score"] > existing["score"]:
                best_by_teacher[teacher.id] = item
        items = sorted(best_by_teacher.values(), key=lambda item: item["score"], reverse=True)[:limit]
        return {
            "intent": "match",
            "project_description": project_description,
            "needs_more_input": False,
            "items": items,
            "total": len(items),
            "message": "已按项目描述匹配在职导师和有效研究方向。" if items else "暂未找到匹配的导师方向。",
        }

    @staticmethod
    def _parse_limit(value: str) -> int:
        match = re.search(r"(?:limit\s*[=:]?|前)\s*(\d+)", value, re.IGNORECASE)
        return max(1, min(int(match.group(1)), 10)) if match else settings.SKILL_RECOMMEND_LIMIT

    @staticmethod
    def _parse_option(query: str, name: str) -> str | None:
        match = re.search(rf"{name}\s*[=:：]\s*([^,，\s]+)", query, re.IGNORECASE)
        return match.group(1).strip() if match else None

    @staticmethod
    def _serialize(
        teacher: User,
        direction: TeacherDirection,
        project_description: str,
        score: float,
    ) -> dict[str, Any]:
        matches = [tag for tag in direction.tags if tag.lower() in project_description.lower()]
        match_text = "、".join(matches[:3]) if matches else direction.title
        return {
            "teacher_id": teacher.id,
            "name": teacher.name,
            "direction_id": direction.id,
            "title": direction.title,
            "description": direction.description,
            "tags": direction.tags,
            "score": round(score, 6),
            "reason": f"推荐理由：项目描述与“{match_text}”方向匹配。",
        }
