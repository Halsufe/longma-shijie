from __future__ import annotations

from typing import Any, Final

from sqlalchemy.orm import Session

from backend.app.core.errors import AppException
from backend.app.models.user import User
from backend.app.repositories.party_repo import PartyRepository
from backend.app.services.party_activity_service import PartyActivityService
from backend.app.services.party_profile_service import PartyProfileService
from backend.app.services.party_registration_service import PartyRegistrationService
from backend.app.services.party_political_material_service import (
    PartyPoliticalMaterialService,
)
from backend.app.services.party_political_status_service import (
    PartyPoliticalStatusService,
)
from backend.app.services.party_stats_service import PartyStatsService


PARTY_SKILL_TOOL_CONTRACTS: Final = {
    "list_party_members": {
        "permission": "admin",
        "description": "党员名册查询（班级/类型/状态筛选）",
        "read_only": True,
    },
    "get_party_member": {
        "permission": "admin/self",
        "description": "党员信息查询",
        "read_only": True,
    },
    "list_party_activities": {
        "permission": "authenticated/visibility",
        "description": "按当前用户可见性查询活动列表",
        "read_only": True,
    },
    "get_party_activity": {
        "permission": "visible_user",
        "description": "按当前用户可见性查询活动详情",
        "read_only": True,
    },
    "get_party_my_records": {
        "permission": "self",
        "description": "查询本人的报名与签到记录",
        "read_only": True,
    },
}
PARTY_SKILL_TOOLS: Final = PARTY_SKILL_TOOL_CONTRACTS
PARTY_SKILL_WRITE_TOOLS: Final[tuple[str, ...]] = ()

# Political extensions are deliberately separate so consumers expecting the
# original M1-M8 five-tool contract remain compatible.
POLITICAL_SKILL_TOOL_CONTRACTS: Final = {
    "get_my_political_status": {
        "permission": "self/student",
        "description": "查询本人政治面貌及最近审核状态",
        "read_only": True,
    },
    "list_political_learning_materials": {
        "permission": "authenticated/visibility",
        "description": "查询当前用户可见的政治学习资料",
        "read_only": True,
    },
    "get_political_status_stats": {
        "permission": "admin",
        "description": "查询政治面貌统计",
        "read_only": True,
    },
}
POLITICAL_SKILL_TOOLS: Final = POLITICAL_SKILL_TOOL_CONTRACTS


class PartySkillBoundary:
    """党建查询 Skill 的只读执行边界；不注册任何写操作。"""

    def __init__(self, db: Session, current_user: User):
        self.db = db
        self.current_user = current_user

    def _require_admin(self) -> None:
        if not self.current_user.is_admin:
            raise AppException("FORBIDDEN", "仅管理员可查询党员名册", 403)

    def list_party_members(
        self,
        *,
        class_name: str | None = None,
        party_type: str | None = None,
        apply_status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        self._require_admin()
        members, total, normalized_page, normalized_size = PartyRepository.list_members(
            self.db,
            class_name=class_name,
            party_type=party_type,
            apply_status=apply_status,
            page=page,
            page_size=page_size,
        )
        return {
            "total": total,
            "page": normalized_page,
            "page_size": normalized_size,
            "items": [PartyProfileService.serialize_member(user) for user in members],
        }

    def get_party_member(self, user_id: int) -> dict[str, Any]:
        if not self.current_user.is_admin and self.current_user.id != user_id:
            raise AppException("FORBIDDEN", "只能查询本人的党员信息", 403)
        user = PartyProfileService.get_member_or_404(self.db, user_id)
        return PartyProfileService.serialize_member(user)

    def list_party_activities(
        self,
        *,
        status: str | None = None,
        category: str | None = None,
        year: int | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        activities, total, normalized_page, normalized_size = (
            PartyActivityService.list_visible(
                self.db,
                self.current_user,
                status=status,
                category=category,
                year=year,
                page=page,
                page_size=page_size,
            )
        )
        return {
            "total": total,
            "page": normalized_page,
            "page_size": normalized_size,
            "items": [
                PartyActivityService.serialize_for_user(
                    self.db, activity, self.current_user
                )
                for activity in activities
            ],
        }

    def get_party_activity(self, activity_id: int) -> dict[str, Any]:
        activity = PartyActivityService.visible_or_404(
            self.db, activity_id, self.current_user
        )
        return PartyActivityService.serialize_for_user(
            self.db, activity, self.current_user
        )

    def get_party_my_records(self) -> dict[str, Any]:
        return PartyRegistrationService.mine(self.db, self.current_user)

    def get_my_political_status(self) -> dict[str, Any]:
        return PartyPoliticalStatusService.mine(self.db, self.current_user)

    def list_political_learning_materials(self) -> dict[str, Any]:
        items = PartyPoliticalMaterialService.visible(self.db, self.current_user)
        return {
            "total": len(items),
            "items": [PartyPoliticalMaterialService._serialize(item) for item in items],
        }

    def get_political_status_stats(
        self,
        *,
        class_name: str | None = None,
        grade: str | None = None,
        political_status: str | None = None,
    ) -> dict[str, Any]:
        self._require_admin()
        result = PartyStatsService.build(
            self.db,
            class_name=class_name,
            grade=grade,
            political_status_filter=political_status,
        )
        return result["political_counts"]
