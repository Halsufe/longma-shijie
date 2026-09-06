"""Unified execution, response generation, and observation for business Skills."""

import json
import logging
import time
from typing import Any

from sqlalchemy.orm import Session

from backend.app.ai.base import get_adapter
from backend.app.ai.business_skills import BUSINESS_SKILL_REGISTRY
from backend.app.ai.business_skills.base import BusinessSkillPermissionError
from backend.app.ai.skills import get_skill_prompt
from backend.app.models.user import User, UserStatus
from backend.app.repositories.skill_repo import SkillCallRepository


logger = logging.getLogger(__name__)


class BusinessSkillService:
    """Single business Skill entry point shared by ChatService and AgentTools."""

    @classmethod
    async def execute(
        cls,
        skill_name: str,
        user_input: str,
        user: User | None,
        db: Session,
    ) -> dict[str, Any]:
        started_at = time.perf_counter()
        normalized_input = " ".join(user_input.strip().split())
        user_id = getattr(user, "id", None)

        try:
            checked_user = cls._validate_user(user)
            executor_type = BUSINESS_SKILL_REGISTRY.get(skill_name)
            if executor_type is None:
                raise ValueError(f"未知业务 Skill: {skill_name}")

            structured = await executor_type().execute(normalized_input, checked_user, db)
            if not isinstance(structured, dict):
                raise TypeError(f"{skill_name} 执行器必须返回 dict")

            response = await cls._generate_response(skill_name, normalized_input, structured)
            result = {
                "skill_name": skill_name,
                "intent": structured.get("intent", "query"),
                "data": structured,
                "response": response,
            }
            cls._record_call(
                db,
                skill_name=skill_name,
                user_id=user_id,
                user_input=normalized_input,
                output=cls._serialize_output(result),
                status="success",
                duration_ms=cls._duration_ms(started_at),
            )
            return result
        except Exception as exc:
            cls._record_call(
                db,
                skill_name=skill_name,
                user_id=user_id,
                user_input=normalized_input,
                output=json.dumps({"error": str(exc)}, ensure_ascii=False),
                status="failed",
                duration_ms=cls._duration_ms(started_at),
                error=str(exc),
            )
            raise

    @staticmethod
    def _validate_user(user: User | None) -> User:
        if user is None or getattr(user, "id", None) is None:
            raise BusinessSkillPermissionError("业务 Skill 需要登录后使用")
        if getattr(user, "deleted_at", None) is not None:
            raise BusinessSkillPermissionError("当前用户不可用")
        if getattr(user, "status", None) == UserStatus.DISABLED.value:
            raise BusinessSkillPermissionError("当前用户已被禁用")
        return user

    @classmethod
    async def _generate_response(
        cls,
        skill_name: str,
        user_input: str,
        structured: dict[str, Any],
    ) -> str:
        adapter = get_adapter()
        if adapter.name == "mock":
            return cls._fallback_response(structured)

        system_prompt = get_skill_prompt(skill_name, user_input)
        payload = json.dumps(structured, ensure_ascii=False, default=str)
        return await adapter.chat(
            [
                {
                    "role": "user",
                    "content": (
                        "请仅依据以下业务执行结果生成简洁中文回复，不得补造数据。"
                        f"\n\n结构化结果：{payload}"
                    ),
                }
            ],
            system_prompt=system_prompt,
        )

    @staticmethod
    def _fallback_response(structured: dict[str, Any]) -> str:
        message = structured.get("message")
        if isinstance(message, str) and message:
            return message
        return json.dumps(structured, ensure_ascii=False, default=str)

    @staticmethod
    def _serialize_output(result: dict[str, Any]) -> str:
        output = json.dumps(result, ensure_ascii=False, default=str)
        return output[:4000]

    @staticmethod
    def _duration_ms(started_at: float) -> int:
        return max(0, int((time.perf_counter() - started_at) * 1000))

    @staticmethod
    def _record_call(
        db: Session,
        *,
        skill_name: str,
        user_id: int | None,
        user_input: str,
        output: str | None,
        status: str,
        duration_ms: int,
        error: str | None = None,
    ) -> None:
        try:
            SkillCallRepository.create(
                db,
                skill_name=skill_name,
                user_id=user_id,
                input=user_input,
                output=output,
                status=status,
                duration_ms=duration_ms,
                error=error,
            )
        except Exception:
            logger.exception("Failed to record business Skill call: skill=%s", skill_name)
