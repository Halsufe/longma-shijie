from typing import Any

from sqlalchemy.orm import Session

from backend.app.core.errors import AppException
from backend.app.models.party import PartyActivity
from backend.app.models.user import User, UserRole
from backend.app.repositories.party_repo import PartyRepository
from backend.app.services.party_activity_service import PartyActivityService
from backend.app.services.party_profile_service import PartyProfileService
from backend.app.services.party_target_roles import matches_target_role
from backend.app.services.party_registration_service import PartyRegistrationService


TIMELINE_LABELS = (
    ("apply_date", "递交入党申请书"),
    ("activist_date", "确定为入党积极分子"),
    ("target_date", "列为发展对象"),
    ("probation_date", "接受为预备党员"),
    ("full_date", "转为正式党员"),
)


class PartyArchiveService:
    @staticmethod
    def serialize_user(user: User) -> dict[str, Any]:
        return {
            "user_id": user.id,
            "student_no": user.student_no,
            "name": user.name,
            "role": user.role,
            "party": user.party,
        }

    @staticmethod
    def member_matches(
        user: User,
        *,
        class_name: str | None = None,
        grade: str | None = None,
        party_type: str | None = None,
        apply_status: str | None = None,
    ) -> bool:
        party = user.party
        if (
            user.role != UserRole.STUDENT.value
            or not party.get("party_type")
            or party.get("deleted_at")
        ):
            return False
        return not (
            (class_name and party.get("class_name") != class_name)
            or (grade and party.get("grade") != grade)
            or (party_type and party.get("party_type") != party_type)
            or (apply_status and party.get("apply_status") != apply_status)
        )

    @staticmethod
    def list_members(
        db: Session,
        *,
        class_name: str | None = None,
        grade: str | None = None,
        party_type: str | None = None,
        apply_status: str | None = None,
    ) -> list[User]:
        return [
            user
            for user in PartyRepository.list_active_users(db)
            if PartyArchiveService.member_matches(
                user,
                class_name=class_name,
                grade=grade,
                party_type=party_type,
                apply_status=apply_status,
            )
        ]

    @staticmethod
    def expected_users(
        db: Session,
        activity: PartyActivity,
        *,
        class_name: str | None = None,
        grade: str | None = None,
    ) -> list[User]:
        users = PartyRepository.list_active_users(db)
        by_id = {user.id: user for user in users}
        if activity.target_roles == "指定人员":
            selected = [
                by_id[user_id]
                for user_id in activity.target_member_ids
                if user_id in by_id
                and by_id[user_id].role != UserRole.ALUMNI.value
            ]
        elif activity.target_roles == "全体学生":
            selected = [user for user in users if user.role == UserRole.STUDENT.value]
        else:
            selected = [
                user for user in users if matches_target_role(user, activity.target_roles)
            ]
        if class_name:
            selected = [
                user for user in selected if user.party.get("class_name") == class_name
            ]
        if grade:
            selected = [user for user in selected if user.party.get("grade") == grade]
        return selected

    @staticmethod
    def activity_archive(db: Session, activity_id: int) -> dict[str, Any]:
        activity = PartyActivityService.get_or_404(db, activity_id)
        if activity.status not in {"finished", "archived"}:
            raise AppException(
                "PARTY_ARCHIVE_NOT_READY", "仅已结束或已归档活动可生成工作档案", 409
            )
        expected = PartyArchiveService.expected_users(db, activity)
        participants = PartyRepository.list_activity_participants(db, activity.id)
        users = PartyRepository.list_users_by_ids(
            db, list({participant.user_id for participant in participants})
        )
        users_by_id = {user.id: user for user in users}
        serialized_participants = []
        for participant in participants:
            user = users_by_id.get(participant.user_id)
            if not user:
                continue
            serialized = PartyRegistrationService.serialize(participant)
            serialized["user"] = PartyArchiveService.serialize_user(user)
            serialized_participants.append(serialized)
        registered = [
            participant
            for participant in participants
            if participant.registration_status == "registered"
        ]
        return {
            "activity": PartyActivityService.serialize(activity),
            "expected_members": [
                PartyArchiveService.serialize_user(user) for user in expected
            ],
            "expected_member_ids": [user.id for user in expected],
            "participants": serialized_participants,
            "expected_count": len(expected),
            "registered_count": len(registered),
            "signed_in_count": sum(
                participant.attendance_status == "signed_in"
                for participant in registered
            ),
            "absent_count": sum(
                participant.attendance_status == "absent"
                for participant in registered
            ),
        }

    @staticmethod
    def member_archive(db: Session, user_id: int) -> dict[str, Any]:
        user = PartyProfileService.get_member_or_404(db, user_id)
        party = user.party
        timeline = [
            {"key": key, "label": label, "date": str(party[key])}
            for key, label in TIMELINE_LABELS
            if party.get(key)
        ]
        return {
            "member": PartyProfileService.serialize_member(user),
            "timeline": timeline,
            "materials": PartyRepository.list_materials(db, user.id),
        }

    @staticmethod
    def list_archives(
        db: Session,
        *,
        year: int | None = None,
        category: str | None = None,
        class_name: str | None = None,
        grade: str | None = None,
        party_type: str | None = None,
        apply_status: str | None = None,
    ) -> dict[str, Any]:
        activities = [
            activity
            for activity in PartyRepository.query_activities(
                db, category=category, year=year
            )
            if activity.status in {"finished", "archived"}
        ]
        members = PartyArchiveService.list_members(
            db,
            class_name=class_name,
            grade=grade,
            party_type=party_type,
            apply_status=apply_status,
        )
        return {
            "activities": [
                PartyActivityService.serialize(activity) for activity in activities
            ],
            "members": [
                PartyProfileService.serialize_member(member) for member in members
            ],
            "activity_total": len(activities),
            "member_total": len(members),
        }
