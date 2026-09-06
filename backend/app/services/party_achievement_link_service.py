from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.app.core.errors import AppException
from backend.app.models.achievement import Achievement, AchievementStatus
from backend.app.models.party import PartyActivity
from backend.app.models.user import User
from backend.app.repositories.achievement_repo import AchievementRepository
from backend.app.repositories.party_repo import PartyRepository
from backend.app.services.achievement_service import (
    AchievementValidationError,
    derive_validated_date,
    validate_details,
    validate_level,
)
from backend.app.services.party_target_roles import LEAGUE_ACTIVITY_CATEGORIES


IDENTITY_LINK_TYPES = {"identity", "party_identity", "member"}
ACTIVITY_LINK_TYPES = {"activity", "party_activity"}
LEAGUE_ACTIVITY_LINK_TYPES = {"league_activity"}
SOCIAL_ACTIVITY_CATEGORIES = {"志愿公益"}


class PartyAchievementLinkService:
    @staticmethod
    def link(
        db: Session,
        *,
        actor: User,
        link_type: str | None,
        activity_id: int | None,
        target_user_id: int | None,
        achievement_category: str | None = None,
    ) -> Achievement:
        target = PartyAchievementLinkService._resolve_target(
            db, actor=actor, target_user_id=target_user_id
        )
        normalized_type = PartyAchievementLinkService._normalize_link_type(
            link_type, activity_id
        )
        if normalized_type == "identity":
            return PartyAchievementLinkService._link_identity(db, target)
        if activity_id is None:
            raise AppException(
                "PARTY_ACHIEVEMENT_ACTIVITY_REQUIRED",
                "活动经历联动必须提供 activity_id",
                422,
            )
        return PartyAchievementLinkService._link_activity(
            db,
            target,
            activity_id,
            league_activity=normalized_type == "league_activity",
            achievement_category=achievement_category,
        )

    @staticmethod
    def _resolve_target(
        db: Session, *, actor: User, target_user_id: int | None
    ) -> User:
        if target_user_id is not None and target_user_id != actor.id and not actor.is_admin:
            raise AppException(
                "PARTY_ACHIEVEMENT_FORBIDDEN",
                "只能联动本人的党建经历",
                403,
            )
        user_id = target_user_id if target_user_id is not None else actor.id
        target = PartyRepository.get_member(db, user_id)
        if not target:
            raise AppException(
                "PARTY_ACHIEVEMENT_USER_NOT_FOUND",
                "联动目标学生不存在",
                404,
            )
        return target

    @staticmethod
    def _normalize_link_type(link_type: str | None, activity_id: int | None) -> str:
        if link_type is None:
            return "activity" if activity_id is not None else "identity"
        normalized = link_type.strip().lower()
        if normalized in IDENTITY_LINK_TYPES:
            if activity_id is not None:
                raise AppException(
                    "PARTY_ACHIEVEMENT_LINK_INVALID",
                    "党员身份联动不能同时提供 activity_id",
                    422,
                )
            return "identity"
        if normalized in ACTIVITY_LINK_TYPES:
            return "activity"
        if normalized in LEAGUE_ACTIVITY_LINK_TYPES:
            return "league_activity"
        raise AppException(
            "PARTY_ACHIEVEMENT_LINK_INVALID",
            "link_type 必须为 identity、activity 或 league_activity",
            422,
        )

    @staticmethod
    def _link_identity(db: Session, target: User) -> Achievement:
        party = target.party
        party_type = party.get("party_type")
        if party.get("deleted_at") or party_type not in {"正式党员", "预备党员"}:
            raise AppException(
                "PARTY_ACHIEVEMENT_IDENTITY_NOT_ELIGIBLE",
                "仅正式党员或预备党员可联动党员身份成果",
                403,
            )
        source_id = f"identity:{target.id}"
        PartyAchievementLinkService._ensure_not_linked(db, target.id, source_id)

        date_value = (
            party.get("full_date") or party.get("party_join_date")
            if party_type == "正式党员"
            else party.get("probation_date")
        )
        year, month = PartyAchievementLinkService._parse_month(
            date_value, field="党员身份生效时间"
        )
        branch_name = str(party.get("branch_name") or "大数据党支部").strip()
        title = f"{branch_name}党员"
        details = {
            "position": party_type,
            "assessment": "合格",
            "honor_title": "无",
            "start_year": year,
            "start_month": month,
            "end_year": "进行中",
            "end_month": "进行中",
        }
        return PartyAchievementLinkService._create(
            db,
            target=target,
            category="organization",
            title=title,
            description=f"{target.name}的党员身份经历",
            details=details,
            source_id=source_id,
        )

    @staticmethod
    def _link_activity(
        db: Session,
        target: User,
        activity_id: int,
        *,
        league_activity: bool = False,
        achievement_category: str | None = None,
    ) -> Achievement:
        activity = PartyRepository.get_activity(db, activity_id)
        if not activity:
            raise AppException("PARTY_ACTIVITY_NOT_FOUND", "党建活动不存在", 404)
        if league_activity and activity.category not in LEAGUE_ACTIVITY_CATEGORIES:
            raise AppException(
                "PARTY_ACHIEVEMENT_LINK_INVALID",
                "league_activity 仅适用于团学活动",
                422,
            )
        if league_activity and achievement_category not in {"organization", "social"}:
            raise AppException(
                "PARTY_ACHIEVEMENT_CATEGORY_REQUIRED",
                "团学活动联动必须指定组织管理或社会实践分类",
                422,
            )
        participant = PartyRepository.get_participant(db, activity.id, target.id)
        if (
            participant is None
            or participant.registration_status != "registered"
            or participant.attendance_status != "signed_in"
        ):
            raise AppException(
                "PARTY_ACHIEVEMENT_ATTENDANCE_REQUIRED",
                "仅已完成签到的党建活动可联动成长档案",
                409,
            )
        source_id = f"activity:{activity.id}"
        PartyAchievementLinkService._ensure_not_linked(db, target.id, source_id)
        category: str = (
            achievement_category
            if league_activity and achievement_category is not None
            else (
                "social"
                if activity.category in SOCIAL_ACTIVITY_CATEGORIES
                else "organization"
            )
        )
        details = PartyAchievementLinkService._activity_details(
            target=target,
            activity=activity,
            category=category,
        )
        return PartyAchievementLinkService._create(
            db,
            target=target,
            category=category,
            title=activity.title,
            description=activity.summary or activity.content,
            details=details,
            source_id=source_id,
        )

    @staticmethod
    def _activity_details(
        *, target: User, activity: PartyActivity, category: str
    ) -> dict[str, Any]:
        start_year = activity.start_at.year
        start_month = activity.start_at.month
        end_year: int | str = activity.end_at.year if activity.end_at else "进行中"
        end_month: int | str = activity.end_at.month if activity.end_at else "进行中"
        if category == "social":
            return {
                "practice_unit": str(
                    activity.location
                    or target.party.get("branch_name")
                    or "大数据党支部"
                ),
                "is_team": True,
                "member_names": target.name,
                "is_leader": False,
                "start_year": start_year,
                "start_month": start_month,
                "end_year": end_year,
                "end_month": end_month,
                "process_description": activity.summary or activity.content or "无",
            }
        return {
            "position": "参与成员",
            "assessment": "合格",
            "honor_title": "无",
            "start_year": start_year,
            "start_month": start_month,
            "end_year": end_year,
            "end_month": end_month,
        }

    @staticmethod
    def _parse_month(value: Any, *, field: str) -> tuple[int, int]:
        text = str(value or "").strip()
        if len(text) != 7 or text[4] != "-":
            raise AppException(
                "PARTY_ACHIEVEMENT_MAPPING_INVALID",
                f"{field}缺失或格式无效，必须为 YYYY-MM",
                422,
            )
        try:
            year, month = int(text[:4]), int(text[5:])
        except ValueError as exc:
            raise AppException(
                "PARTY_ACHIEVEMENT_MAPPING_INVALID",
                f"{field}缺失或格式无效，必须为 YYYY-MM",
                422,
            ) from exc
        if not 1900 <= year <= 9999 or not 1 <= month <= 12:
            raise AppException(
                "PARTY_ACHIEVEMENT_MAPPING_INVALID",
                f"{field}缺失或格式无效，必须为 YYYY-MM",
                422,
            )
        return year, month

    @staticmethod
    def _ensure_not_linked(db: Session, user_id: int, source_id: str) -> None:
        achievements = (
            db.query(Achievement)
            .filter(
                Achievement.user_id == user_id,
                Achievement.deleted_at.is_(None),
            )
            .all()
        )
        if any(
            item.details.get("source_type") == "party"
            and str(item.details.get("source_id")) == source_id
            for item in achievements
        ):
            raise AppException(
                "PARTY_ACHIEVEMENT_DUPLICATE",
                "该党建经历已联动成长档案",
                409,
            )

    @staticmethod
    def _create(
        db: Session,
        *,
        target: User,
        category: str,
        title: str,
        description: str,
        details: dict[str, Any],
        source_id: str,
    ) -> Achievement:
        details_with_source = {
            **details,
            "source_type": "party",
            "source_id": source_id,
        }
        try:
            normalized = validate_details(category, details_with_source)
            achievement_date = derive_validated_date(category, normalized)
            level = validate_level(category, None)
        except AchievementValidationError as exc:
            raise AppException(
                "PARTY_ACHIEVEMENT_TEMPLATE_INVALID",
                f"党建经历无法映射到成长档案模板: {exc}",
                422,
            ) from exc
        return AchievementRepository.create(
            db,
            target.id,
            category=category,
            title=title,
            description=description,
            achievement_date=achievement_date,
            level=level,
            status=AchievementStatus.PENDING,
            is_public=False,
            member_ids=[],
            proofs=[],
            details=normalized,
        )
