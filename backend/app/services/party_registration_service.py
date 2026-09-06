from datetime import timedelta
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.database import local_now
from backend.app.core.errors import AppException
from backend.app.models.party import PartyActivity, PartyActivityParticipant
from backend.app.models.user import User
from backend.app.repositories.party_repo import PartyRepository
from backend.app.services.party_activity_service import PartyActivityService, _comparable
from backend.app.services.party_notify_adapter import PartyNotifyAdapter


class PartyRegistrationService:
    @staticmethod
    def serialize(participant: PartyActivityParticipant) -> dict[str, Any]:
        return {
            "id": participant.id,
            "activity_id": participant.activity_id,
            "user_id": participant.user_id,
            "registration_status": participant.registration_status,
            "attendance_status": participant.attendance_status,
            "sign_in_time": participant.sign_in_time,
            "sign_in_method": participant.sign_in_method,
            "created_at": participant.created_at,
            "updated_at": participant.updated_at,
        }

    @staticmethod
    def _student_or_403(user: User) -> None:
        if not user.is_student:
            raise AppException(
                "PARTY_REGISTRATION_FORBIDDEN", "党建活动报名仅对在校学生开放", 403
            )

    @staticmethod
    def _activity_for_registration(db: Session, activity_id: int) -> PartyActivity:
        activity = PartyActivityService.get_or_404(db, activity_id)
        if activity.status != "published":
            raise AppException(
                "PARTY_REGISTRATION_CLOSED", "仅已发布且尚未开始的活动可报名", 409
            )
        if activity.registration_deadline is None:
            raise AppException(
                "PARTY_REGISTRATION_DISABLED", "该活动无需自主报名", 409
            )
        return activity

    @staticmethod
    def _before_deadline(activity: PartyActivity) -> None:
        deadline = activity.registration_deadline
        if deadline is None or _comparable(local_now()) >= _comparable(deadline):
            raise AppException(
                "PARTY_REGISTRATION_DEADLINE_PASSED", "报名已截止", 409
            )

    @staticmethod
    def register(
        db: Session, activity_id: int, user: User
    ) -> PartyActivityParticipant:
        PartyRegistrationService._student_or_403(user)
        activity = PartyRegistrationService._activity_for_registration(db, activity_id)
        PartyRegistrationService._before_deadline(activity)
        if not PartyActivityService.is_visible(activity, user):
            raise AppException(
                "PARTY_REGISTRATION_NOT_ELIGIBLE", "您不在该活动的参加对象范围内", 403
            )

        participant = PartyRepository.get_participant(db, activity.id, user.id)
        if participant and participant.registration_status == "registered":
            raise AppException(
                "PARTY_REGISTRATION_DUPLICATE", "您已报名该活动", 409
            )
        if (
            activity.max_participants is not None
            and PartyRepository.count_registered(db, activity.id)
            >= activity.max_participants
        ):
            raise AppException("PARTY_REGISTRATION_FULL", "活动报名名额已满", 409)

        if participant:
            participant.registration_status = "registered"
            participant.attendance_status = "none"
            participant.sign_in_time = None
            participant.sign_in_method = None
            db.add(participant)
        else:
            participant = PartyRepository.create_participant(
                db, activity_id=activity.id, user_id=user.id
            )
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise AppException(
                "PARTY_REGISTRATION_DUPLICATE", "您已报名该活动", 409
            ) from exc
        db.refresh(participant)
        PartyNotifyAdapter.notify_party_registration_result(
            db,
            participant_id=participant.id,
            user_id=user.id,
            activity_title=activity.title,
            registration_status=participant.registration_status,
        )
        return participant

    @staticmethod
    def cancel(
        db: Session, activity_id: int, user: User
    ) -> PartyActivityParticipant:
        PartyRegistrationService._student_or_403(user)
        activity = PartyRegistrationService._activity_for_registration(db, activity_id)
        PartyRegistrationService._before_deadline(activity)
        participant = PartyRepository.get_participant(db, activity.id, user.id)
        if not participant or participant.registration_status != "registered":
            raise AppException("PARTY_REGISTRATION_NOT_FOUND", "您尚未报名该活动", 409)
        if participant.attendance_status == "signed_in":
            raise AppException(
                "PARTY_REGISTRATION_ALREADY_SIGNED_IN", "已签到的报名不可取消", 409
            )
        participant.registration_status = "cancelled"
        participant.attendance_status = "none"
        participant.sign_in_time = None
        participant.sign_in_method = None
        db.add(participant)
        db.commit()
        db.refresh(participant)
        PartyNotifyAdapter.notify_party_registration_result(
            db,
            participant_id=participant.id,
            user_id=user.id,
            activity_title=activity.title,
            registration_status=participant.registration_status,
        )
        return participant

    @staticmethod
    def sign_in(
        db: Session, activity_id: int, user: User
    ) -> PartyActivityParticipant:
        PartyRegistrationService._student_or_403(user)
        activity = PartyActivityService.get_or_404(db, activity_id)
        participant = PartyRepository.get_participant(db, activity.id, user.id)
        if not participant or participant.registration_status != "registered":
            raise AppException("PARTY_REGISTRATION_NOT_FOUND", "请先报名该活动", 409)
        if participant.attendance_status == "signed_in":
            raise AppException("PARTY_ATTENDANCE_DUPLICATE", "您已完成签到", 409)

        now = local_now()
        window = timedelta(minutes=settings.PARTY_SIGN_IN_WINDOW_MINUTES)
        if not (
            _comparable(activity.start_at - window)
            <= _comparable(now)
            <= _comparable(activity.start_at + window)
        ):
            raise AppException(
                "PARTY_SIGN_IN_WINDOW_CLOSED", "当前不在活动签到时间窗口内", 409
            )
        participant.attendance_status = "signed_in"
        participant.sign_in_time = now
        participant.sign_in_method = "self"
        db.add(participant)
        db.commit()
        db.refresh(participant)
        PartyNotifyAdapter.notify_party_attendance_result(
            db,
            participant_id=participant.id,
            user_id=user.id,
            activity_title=activity.title,
            attendance_status=participant.attendance_status,
        )
        return participant

    @staticmethod
    def set_attendance(
        db: Session,
        activity_id: int,
        user_id: int,
        attendance_status: str,
    ) -> PartyActivityParticipant:
        activity = PartyActivityService.get_or_404(db, activity_id)
        participant = PartyRepository.get_participant(db, activity_id, user_id)
        if not participant or participant.registration_status != "registered":
            raise AppException(
                "PARTY_PARTICIPANT_NOT_FOUND", "该用户没有有效报名记录", 404
            )
        participant.attendance_status = attendance_status
        if attendance_status == "signed_in":
            participant.sign_in_time = local_now()
            participant.sign_in_method = "manual"
        else:
            participant.sign_in_time = None
            participant.sign_in_method = None
        db.add(participant)
        db.commit()
        db.refresh(participant)
        PartyNotifyAdapter.notify_party_attendance_result(
            db,
            participant_id=participant.id,
            user_id=user_id,
            activity_title=activity.title,
            attendance_status=participant.attendance_status,
        )
        return participant

    @staticmethod
    def mine(db: Session, user: User) -> dict[str, Any]:
        PartyRegistrationService._student_or_403(user)
        records = []
        for participant, activity in PartyRepository.list_user_participants(db, user.id):
            serialized = PartyRegistrationService.serialize(participant)
            serialized.update(
                {
                    "activity": PartyActivityService.serialize(activity),
                    "title": activity.title,
                    "category": activity.category,
                    "start_at": activity.start_at,
                    "end_at": activity.end_at,
                    "location": activity.location,
                }
            )
            records.append(serialized)
        return {
            "party": user.party,
            "records": records,
            "participation_records": records,
        }
