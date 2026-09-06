"""Current-user achievement management business Skill."""

import hashlib
import json
import re
from typing import Any

from sqlalchemy.orm import Session

from backend.app.ai.business_skills.base import BusinessSkillExecutor
from backend.app.core.confirmation import ConfirmationManager, require_confirmation_token
from backend.app.core.errors import AppException
from backend.app.models.user import User
from backend.app.repositories.achievement_repo import AchievementRepository
from backend.app.repositories.audit_repo import AuditRepository
from backend.app.services.achievement_files import AchievementFileService
from backend.app.services.achievement_service import (
    AchievementValidationError,
    derive_validated_date,
    validate_category,
    validate_details,
    validate_level,
)
from backend.app.services.achievement_templates import serialize_templates


class AchievementManageExecutor(BusinessSkillExecutor):
    skill_name = "achievement_manage"

    async def execute(self, user_input: str, user: User, db: Session) -> dict[str, Any]:
        request = self.normalize_input(user_input)
        action = self._parse_action(request)
        if action == "query":
            return self._query(request, user, db)

        payload = self._parse_payload(request)
        if payload is None:
            return {
                "intent": action,
                "requires_confirmation": False,
                "status": "needs_input",
                "message": "请在操作说明后提供 JSON 数据，包含成果字段或 achievement_id。",
            }
        token = payload.pop("confirmation_token", None)
        try:
            if action == "create":
                return self._create(payload, token, user, db)
            achievement_id = self._achievement_id(payload)
            if action == "update":
                return self._update(achievement_id, payload, token, user, db)
            return self._delete(achievement_id, token, user, db)
        except Exception as exc:
            self._audit(db, user, action, payload.get("achievement_id"), "failed", token, str(exc))
            raise

    def _query(self, request: str, user: User, db: Session) -> dict[str, Any]:
        if "模板" in request or "需要哪些字段" in request:
            templates = serialize_templates()
            category = self._parse_option(request, "category")
            data = {category: templates[category]} if category in templates else templates
            return {
                "intent": "query",
                "query_type": "templates",
                "owner_user_id": user.id,
                "templates": data,
                "total": len(data),
                "message": "已返回成果模板和必填字段。",
            }

        achievement_id = self._parse_id(request)
        if achievement_id is not None:
            achievement = AchievementRepository.get_by_id_for_user(db, achievement_id, user.id)
            if achievement is None:
                raise AppException("NOT_FOUND", "成果不存在", 404)
            return {
                "intent": "query",
                "query_type": "detail",
                "owner_user_id": user.id,
                "item": self._serialize(achievement),
                "total": 1,
                "message": "已查询本人成果详情。",
            }

        items, _ = AchievementRepository.list_by_user(
            db,
            user.id,
            page=1,
            page_size=100,
            category=self._parse_option(request, "category"),
            status=self._parse_option(request, "status"),
            year=self._parse_year(request),
        )
        keyword = self._parse_option(request, "keyword")
        if keyword:
            items = [
                item for item in items
                if keyword.lower() in f"{item.title} {item.description or ''}".lower()
            ]
        return {
            "intent": "query",
            "query_type": "list",
            "owner_user_id": user.id,
            "items": [self._serialize(item) for item in items],
            "total": len(items),
            "message": "已查询当前用户本人的成果。",
        }

    def _create(
        self,
        payload: dict[str, Any],
        token: str | None,
        user: User,
        db: Session,
    ) -> dict[str, Any]:
        if not payload.get("proofs"):
            return {
                "intent": "create",
                "status": "needs_proof",
                "requires_confirmation": False,
                "message": "请先上传至少 1 份证明材料，或到“我的成果”页补充后再提交。",
            }
        if token is None:
            return self._preview("create", payload, user)
        require_confirmation_token("achievement.create", token, payload, user.id)
        normalized = self._normalize_create(payload, user.id)
        achievement = AchievementRepository.create(db, user.id, **normalized)
        self._audit(db, user, "create", achievement.id, "success", token)
        return {
            "intent": "create",
            "status": "success",
            "requires_confirmation": False,
            "item": self._serialize(achievement),
            "message": "成果已创建并进入待审核状态。",
        }

    def _update(
        self,
        achievement_id: int,
        payload: dict[str, Any],
        token: str | None,
        user: User,
        db: Session,
    ) -> dict[str, Any]:
        achievement = AchievementRepository.get_by_id_for_user(db, achievement_id, user.id)
        if achievement is None:
            raise AppException("NOT_FOUND", "成果不存在", 404)
        changes = {key: value for key, value in payload.items() if key != "achievement_id"}
        confirmation_data = {"achievement_id": achievement_id, **changes}
        if token is None:
            return self._preview("update", confirmation_data, user)
        require_confirmation_token("achievement.update", token, confirmation_data, user.id)

        category = str(changes.get("category", achievement.category))
        validate_category(category)
        details = changes.get("details", achievement.details)
        if details:
            changes["details"] = validate_details(category, details)
            changes["level"] = validate_level(category, changes.get("level", achievement.level))
            changes["achievement_date"] = derive_validated_date(category, changes["details"])
        if "proofs" in changes:
            proofs = AchievementFileService.normalize_proofs(changes["proofs"])
            AchievementFileService.validate_owned(user.id, proofs)
            changes["proofs"] = proofs
        changes["status"] = "pending"
        updated = AchievementRepository.update(db, achievement, **changes)
        self._audit(db, user, "update", updated.id, "success", token)
        return {
            "intent": "update",
            "status": "success",
            "requires_confirmation": False,
            "item": self._serialize(updated),
            "message": "成果已更新并重新进入待审核状态。",
        }

    def _delete(
        self,
        achievement_id: int,
        token: str | None,
        user: User,
        db: Session,
    ) -> dict[str, Any]:
        achievement = AchievementRepository.get_by_id_for_user(db, achievement_id, user.id)
        if achievement is None:
            raise AppException("NOT_FOUND", "成果不存在", 404)
        confirmation_data = {"achievement_id": achievement_id}
        if token is None:
            return self._preview("delete", confirmation_data, user)
        require_confirmation_token("achievement.delete", token, confirmation_data, user.id)
        AchievementRepository.soft_delete(db, achievement)
        self._audit(db, user, "delete", achievement_id, "success", token)
        return {
            "intent": "delete",
            "status": "success",
            "requires_confirmation": False,
            "achievement_id": achievement_id,
            "message": "成果已删除。",
        }

    @staticmethod
    def _normalize_create(payload: dict[str, Any], user_id: int) -> dict[str, Any]:
        category = str(payload.get("category", ""))
        validate_category(category)
        details = validate_details(category, payload.get("details"))
        normalized = dict(payload)
        normalized["details"] = details
        normalized["level"] = validate_level(category, payload.get("level"))
        normalized["achievement_date"] = derive_validated_date(category, details)
        proofs = AchievementFileService.normalize_proofs(payload.get("proofs"))
        AchievementFileService.validate_owned(user_id, proofs)
        normalized["proofs"] = proofs
        normalized["status"] = "pending"
        return normalized

    @staticmethod
    def _preview(action: str, data: dict[str, Any], user: User) -> dict[str, Any]:
        operation = f"achievement.{action}"
        confirmation = ConfirmationManager.create_confirmation(user.id, operation, data)
        title = data.get("title") or f"成果 #{data.get('achievement_id', '')}"
        return {
            "intent": action,
            "status": "pending_confirmation",
            "requires_confirmation": True,
            "preview": {
                "operation": operation,
                "summary": title,
                "fields": data,
                "impact": "仅影响当前用户本人的成果；修改后需重新审核。",
            },
            **confirmation,
            "message": "请确认预览内容后，携带 confirmation_token 再次提交相同数据。",
        }

    @staticmethod
    def _audit(
        db: Session,
        user: User,
        action: str,
        target_id: Any,
        result: str,
        token: str | None,
        error: str | None = None,
    ) -> None:
        token_hash = hashlib.sha256(token.encode()).hexdigest() if token else None
        AuditRepository.create(
            db,
            operator_id=user.id,
            operator_name=user.name,
            action=f"achievement.{action}",
            target_type="achievement",
            target_id=str(target_id) if target_id is not None else None,
            result=result,
            detail={"confirmation_token_hash": token_hash, "error": error},
        )

    @staticmethod
    def _serialize(achievement: Any) -> dict[str, Any]:
        return {
            "id": achievement.id,
            "user_id": achievement.user_id,
            "category": achievement.category,
            "title": achievement.title,
            "description": achievement.description,
            "achievement_date": achievement.achievement_date,
            "level": achievement.level,
            "status": achievement.status,
            "is_public": achievement.is_public,
            "member_ids": achievement.member_ids,
            "proofs": achievement.proofs,
            "details": achievement.details,
        }

    @staticmethod
    def _parse_action(user_input: str) -> str:
        action_terms = {
            "delete": ("删除", "移除"),
            "update": ("修改", "更新", "编辑"),
            "create": ("新增", "创建", "录入", "添加"),
        }
        for action, terms in action_terms.items():
            if any(term in user_input for term in terms):
                return action
        return "query"

    @staticmethod
    def _parse_payload(request: str) -> dict[str, Any] | None:
        start = request.find("{")
        end = request.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            value = json.loads(request[start:end + 1])
        except json.JSONDecodeError as exc:
            raise AppException("ACHIEVEMENT_INPUT_INVALID", "成果 JSON 数据格式错误", 422) from exc
        if not isinstance(value, dict):
            raise AppException("ACHIEVEMENT_INPUT_INVALID", "成果数据必须是 JSON 对象", 422)
        return value

    @staticmethod
    def _achievement_id(payload: dict[str, Any]) -> int:
        value = payload.get("achievement_id")
        if isinstance(value, bool) or not str(value or "").isdigit():
            raise AppException("ACHIEVEMENT_INPUT_INVALID", "请提供有效的 achievement_id", 422)
        return int(str(value))

    @staticmethod
    def _parse_option(request: str, name: str) -> str | None:
        match = re.search(rf"{name}\s*[=:：]\s*([^,，\s]+)", request, re.IGNORECASE)
        return match.group(1).strip() if match else None

    @staticmethod
    def _parse_id(request: str) -> int | None:
        match = re.search(r"(?:achievement_id|成果)\s*[=:：#]?\s*(\d+)", request, re.IGNORECASE)
        return int(match.group(1)) if match else None

    @staticmethod
    def _parse_year(request: str) -> str | None:
        match = re.search(r"(20\d{2})\s*年?", request)
        return match.group(1) if match else None
