from collections import Counter
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.app.core.database import local_now
from backend.app.core.pagination import normalize_page, normalize_page_size
from backend.app.models.party import PartyActivity, PoliticalLearningMaterial
from backend.app.models.user import User
from backend.app.repositories.party_repo import PartyRepository
from backend.app.services.party_archive_service import PartyArchiveService
from backend.app.services.party_target_roles import (
    LEAGUE_ACTIVITY_CATEGORIES,
    political_status,
)


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _groups(counter: Counter[str]) -> list[dict[str, Any]]:
    return [
        {"key": key, "label": key, "count": count}
        for key, count in sorted(counter.items())
    ]


def _month(value: Any, fallback: datetime) -> str:
    if value:
        text = str(value)
        if len(text) >= 7:
            return text[:7]
    return fallback.strftime("%Y-%m")


class PartyStatsService:
    @staticmethod
    def build(
        db: Session,
        *,
        class_name: str | None = None,
        grade: str | None = None,
        year: int | None = None,
        category: str | None = None,
        political_status_filter: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        members = PartyArchiveService.list_members(
            db, class_name=class_name, grade=grade
        )
        member_counts = PartyStatsService._member_counts(members)
        activities = PartyRepository.query_activities(
            db, category=category, year=year
        )
        participation = PartyStatsService._participation(
            db,
            [activity for activity in activities if activity.status != "draft"],
            class_name=class_name,
            grade=grade,
            page=page,
            page_size=page_size,
        )
        materials = PartyStatsService._materials(
            db,
            PartyRepository.query_activities(db, category=category),
            class_name=class_name,
            grade=grade,
            year=year,
        )
        report_year = year or local_now().year
        development = PartyStatsService._development(members, report_year)
        all_students = [
            user for user in PartyRepository.list_active_users(db) if user.is_student
        ]
        political_counts = PartyStatsService._political_counts(
            all_students,
            class_name=class_name,
            grade=grade,
            political_status_filter=political_status_filter,
        )
        league_activities = [
            activity
            for activity in activities
            if activity.category in LEAGUE_ACTIVITY_CATEGORIES
        ]
        league_participation = PartyStatsService._participation(
            db,
            [activity for activity in league_activities if activity.status != "draft"],
            class_name=class_name,
            grade=grade,
            page=page,
            page_size=page_size,
            political_status_filter=political_status_filter,
        )
        political_materials = PartyStatsService._political_materials(
            db, year=year, political_status_filter=political_status_filter
        )
        return {
            "member_counts": member_counts,
            "participation": participation,
            "materials": materials,
            "development": development,
            "political_counts": political_counts,
            "league_participation": league_participation,
            "political_materials": political_materials,
            "filters": {
                "class_name": class_name,
                "grade": grade,
                "year": year,
                "category": category,
                "political_status": political_status_filter,
            },
        }

    @staticmethod
    def _member_counts(members: list[User]) -> dict[str, Any]:
        return {
            "total": len(members),
            "by_party_type": _groups(
                Counter(str(user.party.get("party_type")) for user in members)
            ),
            "by_class": _groups(
                Counter(str(user.party.get("class_name") or "未设置") for user in members)
            ),
            "by_grade": _groups(
                Counter(str(user.party.get("grade") or "未设置") for user in members)
            ),
        }

    @staticmethod
    def _participation(
        db: Session,
        activities: list[PartyActivity],
        *,
        class_name: str | None,
        grade: str | None,
        page: int,
        page_size: int,
        political_status_filter: str | None = None,
    ) -> dict[str, Any]:
        rows = []
        total_expected = total_registered = total_signed = 0
        for activity in activities:
            expected = PartyArchiveService.expected_users(
                db, activity, class_name=class_name, grade=grade
            )
            participants = PartyRepository.list_activity_participants(db, activity.id)
            participant_users = {
                user.id: user
                for user in PartyRepository.list_users_by_ids(
                    db, [participant.user_id for participant in participants]
                )
            }
            registered = []
            for participant in participants:
                user = participant_users.get(participant.user_id)
                if not user or participant.registration_status != "registered":
                    continue
                if class_name and user.party.get("class_name") != class_name:
                    continue
                if grade and user.party.get("grade") != grade:
                    continue
                if political_status_filter and political_status(user) != political_status_filter:
                    continue
                registered.append(participant)
            signed = [
                participant
                for participant in registered
                if participant.attendance_status == "signed_in"
            ]
            expected_count = len(expected)
            if political_status_filter:
                expected_count = sum(
                    political_status(user) == political_status_filter
                    for user in expected
                )
            registered_count = len(registered)
            signed_count = len(signed)
            total_expected += expected_count
            total_registered += registered_count
            total_signed += signed_count
            rows.append(
                {
                    "activity_id": activity.id,
                    "title": activity.title,
                    "expected_count": expected_count,
                    "registered_count": registered_count,
                    "signed_in_count": signed_count,
                    "participation_rate": _rate(signed_count, expected_count),
                    "registration_rate": _rate(registered_count, expected_count),
                }
            )
        normalized_page = normalize_page(page)
        normalized_size = normalize_page_size(page_size)
        start = (normalized_page - 1) * normalized_size
        return {
            "expected_count": total_expected,
            "registered_count": total_registered,
            "signed_in_count": total_signed,
            "expected": total_expected,
            "registered": total_registered,
            "signed_in": total_signed,
            "participation_rate": _rate(total_signed, total_expected),
            "registration_rate": _rate(total_registered, total_expected),
            "activities": rows[start : start + normalized_size],
            "total": len(rows),
            "page": normalized_page,
            "page_size": normalized_size,
        }

    @staticmethod
    def _political_counts(
        users: list[User],
        *,
        class_name: str | None,
        grade: str | None,
        political_status_filter: str | None,
    ) -> dict[str, Any]:
        selected = [
            user
            for user in users
            if (not class_name or user.party.get("class_name") == class_name)
            and (not grade or user.party.get("grade") == grade)
            and (
                not political_status_filter
                or political_status(user) == political_status_filter
            )
        ]
        return {
            "total": len(selected),
            "by_status": _groups(Counter(political_status(user) for user in selected)),
            "by_class": _groups(
                Counter(str(user.party.get("class_name") or "未设置") for user in selected)
            ),
            "by_grade": _groups(
                Counter(str(user.party.get("grade") or "未设置") for user in selected)
            ),
        }

    @staticmethod
    def _political_materials(
        db: Session, *, year: int | None, political_status_filter: str | None
    ) -> dict[str, Any]:
        query = db.query(PoliticalLearningMaterial).filter(
            PoliticalLearningMaterial.deleted_at.is_(None)
        )
        if year is not None:
            query = query.filter(
                PoliticalLearningMaterial.created_at >= datetime(year, 1, 1)
            ).filter(
                PoliticalLearningMaterial.created_at < datetime(year + 1, 1, 1)
            )
        items = query.all()
        if political_status_filter:
            items = [
                item
                for item in items
                if political_status_filter in item.applicable_roles
                or "全体学生" in item.applicable_roles
            ]
        months: Counter[str] = Counter()
        categories: Counter[str] = Counter()
        for item in items:
            months[item.created_at.strftime("%Y-%m")] += 1
            for role in item.applicable_roles or ["未指定"]:
                categories[role] += 1
        return {
            "total": len(items),
            "by_month": _groups(months),
            "by_category": _groups(categories),
        }

    @staticmethod
    def _materials(
        db: Session,
        activities: list[PartyActivity],
        *,
        class_name: str | None,
        grade: str | None,
        year: int | None,
    ) -> dict[str, Any]:
        month_counts: Counter[str] = Counter()
        by_activity = []
        activity_total = 0
        for activity in activities:
            attachments = []
            for attachment in activity.materials:
                month = _month(attachment.get("uploaded_at"), activity.created_at)
                if year is not None and not month.startswith(f"{year:04d}-"):
                    continue
                attachments.append((attachment, month))
            count = len(attachments)
            activity_total += count
            by_activity.append(
                {"activity_id": activity.id, "title": activity.title, "count": count}
            )
            for _, month in attachments:
                month_counts[month] += 1

        members = {
            user.id: user
            for user in PartyArchiveService.list_members(
                db, class_name=class_name, grade=grade
            )
        }
        member_counts: Counter[int] = Counter()
        member_total = 0
        for material in PartyRepository.list_active_materials(db):
            if material.user_id not in members:
                continue
            if year is not None and material.uploaded_at.year != year:
                continue
            member_total += 1
            member_counts[material.user_id] += 1
            month_counts[material.uploaded_at.strftime("%Y-%m")] += 1
        by_member = [
            {
                "user_id": user_id,
                "name": members[user_id].name,
                "count": count,
            }
            for user_id, count in sorted(member_counts.items())
        ]
        return {
            "total": activity_total + member_total,
            "activity_materials": activity_total,
            "member_materials": member_total,
            "learning_materials": activity_total,
            "development_materials": member_total,
            "by_month": _groups(month_counts),
            "by_activity": by_activity,
            "by_member": by_member,
        }

    @staticmethod
    def _development(members: list[User], report_year: int) -> dict[str, Any]:
        by_status = _groups(
            Counter(str(user.party.get("apply_status") or "未设置") for user in members)
        )
        annual = sum(
            str(user.party.get("full_date") or "").startswith(f"{report_year:04d}-")
            for user in members
        )
        return {
            "by_status": by_status,
            "annual_full_count": annual,
            "annual_conversions": annual,
        }
