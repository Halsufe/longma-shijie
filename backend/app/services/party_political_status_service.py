from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from backend.app.core.database import local_now
from backend.app.core.errors import AppException
from backend.app.models.audit import AuditLog
from backend.app.models.party import PoliticalStatusReview
from backend.app.models.user import User
from backend.app.repositories.party_repo import PartyRepository
from backend.app.services.party_notify_adapter import PartyNotifyAdapter


POLITICAL_STATUSES = {
    "中共党员",
    "预备党员",
    "入党积极分子",
    "共青团员",
    "群众",
}
STUDENT_APPLICABLE_STATUSES = {"共青团员", "群众"}
PARTY_TYPE_TO_POLITICAL_STATUS = {
    "正式党员": "中共党员",
    "预备党员": "预备党员",
    "入党积极分子": "入党积极分子",
}


class PartyPoliticalStatusService:
    @staticmethod
    def effective_status(user: User) -> str:
        value = getattr(user, "political_status", None)
        return value if value in POLITICAL_STATUSES else "群众"

    @staticmethod
    def _require_student(user: User) -> None:
        if not user.is_student:
            raise AppException(
                "POLITICAL_STATUS_STUDENT_REQUIRED",
                "仅在校学生可申请政治面貌变更",
                403,
            )

    @staticmethod
    def serialize_review(db: Session, review: PoliticalStatusReview) -> dict[str, Any]:
        user = PartyRepository.get_user(db, review.user_id)
        return {
            "id": review.id,
            "user_id": review.user_id,
            "student_no": user.student_no if user else "",
            "user_name": user.name if user else "",
            "from_status": review.from_status,
            "to_status": review.to_status,
            "status": review.status,
            "submitted_by": review.submitted_by,
            "submitted_at": review.submitted_at,
            "reviewed_by": review.reviewed_by,
            "reviewed_at": review.reviewed_at,
            "remark": review.remark,
        }

    @staticmethod
    def mine(db: Session, user: User) -> dict[str, Any]:
        PartyPoliticalStatusService._require_student(user)
        latest = PartyRepository.latest_political_review(db, user.id)
        return {
            "political_status": PartyPoliticalStatusService.effective_status(user),
            "political_status_updated_at": user.political_status_updated_at,
            "latest_review": (
                PartyPoliticalStatusService.serialize_review(db, latest)
                if latest
                else None
            ),
        }

    @staticmethod
    def apply(
        db: Session, user: User, *, to_status: str, remark: str | None
    ) -> PoliticalStatusReview:
        PartyPoliticalStatusService._require_student(user)
        if to_status not in STUDENT_APPLICABLE_STATUSES:
            raise AppException(
                "POLITICAL_STATUS_INVALID",
                "学生只能申请共青团员或群众；党员类由党员档案同步",
                422,
            )
        current = PartyPoliticalStatusService.effective_status(user)
        if current == to_status:
            raise AppException(
                "POLITICAL_STATUS_UNCHANGED", "目标政治面貌与当前状态相同", 409
            )
        pending = PartyRepository.pending_political_review(db, user.id)
        if pending:
            message = (
                "相同政治面貌申请正在审核中"
                if pending.to_status == to_status
                else "已有政治面貌申请正在审核中"
            )
            raise AppException("POLITICAL_STATUS_REVIEW_PENDING", message, 409)
        review = PartyRepository.create_political_review(
            db,
            user_id=user.id,
            from_status=current,
            to_status=to_status,
            status="pending",
            submitted_by=user.id,
            submitted_at=local_now(),
            remark=(remark or "").strip() or None,
        )
        db.commit()
        db.refresh(review)
        return review

    @staticmethod
    def list_reviews(
        db: Session,
        *,
        status: str | None,
        user_id: int | None,
        to_status: str | None,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        if status and status not in {"pending", "approved", "rejected"}:
            raise AppException("POLITICAL_REVIEW_STATUS_INVALID", "审核状态无效", 422)
        if to_status and to_status not in POLITICAL_STATUSES:
            raise AppException("POLITICAL_STATUS_INVALID", "政治面貌筛选值无效", 422)
        items, total, page, page_size = PartyRepository.list_political_reviews(
            db,
            status=status,
            user_id=user_id,
            to_status=to_status,
            page=page,
            page_size=page_size,
        )
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                PartyPoliticalStatusService.serialize_review(db, item)
                for item in items
            ],
        }

    @staticmethod
    def serialize_roster_user(db: Session, user: User) -> dict[str, Any]:
        party = user.party
        profile = user.profile
        latest = PartyRepository.latest_political_review(db, user.id)
        return {
            "user_id": user.id,
            "student_no": user.student_no,
            "name": user.name,
            "political_status": PartyPoliticalStatusService.effective_status(user),
            "political_status_updated_at": user.political_status_updated_at,
            "class_name": party.get("class_name") or profile.get("class_name"),
            "grade": party.get("grade") or profile.get("grade"),
            "party_type": party.get("party_type"),
            "apply_status": party.get("apply_status"),
            "latest_review": (
                PartyPoliticalStatusService.serialize_review(db, latest)
                if latest
                else None
            ),
        }

    @staticmethod
    def list_roster(
        db: Session,
        *,
        q: str | None,
        political_status: str | None,
        class_name: str | None,
        grade: str | None,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        if political_status and political_status not in POLITICAL_STATUSES:
            raise AppException("POLITICAL_STATUS_INVALID", "政治面貌筛选值无效", 422)
        items, total, page, page_size = PartyRepository.list_political_roster(
            db,
            q=q,
            political_status=political_status,
            class_name=class_name,
            grade=grade,
            page=page,
            page_size=page_size,
        )
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                PartyPoliticalStatusService.serialize_roster_user(db, user)
                for user in items
            ],
        }

    @staticmethod
    def review(
        db: Session,
        review_id: int,
        *,
        approve: bool,
        operator: User,
        remark: str | None,
    ) -> PoliticalStatusReview:
        review = PartyRepository.get_political_review(db, review_id)
        if not review:
            raise AppException(
                "POLITICAL_STATUS_REVIEW_NOT_FOUND", "政治面貌申请不存在", 404
            )
        if review.status != "pending":
            raise AppException(
                "POLITICAL_STATUS_REVIEW_COMPLETED", "该申请已经审核，不能重复操作", 409
            )
        user = PartyRepository.get_user(db, review.user_id)
        if not user:
            raise AppException("USER_NOT_FOUND", "申请用户不存在", 404)
        now = local_now()
        review.status = "approved" if approve else "rejected"
        review.reviewed_by = operator.id
        review.reviewed_at = now
        review.remark = (remark or "").strip() or review.remark
        if approve:
            user.political_status = review.to_status
            user.political_status_updated_at = now
            db.add(user)
        db.add(review)
        db.add(
            AuditLog(
                operator_id=operator.id,
                operator_name=operator.name,
                action=f"political_status_{review.status}",
                target_type="political_status_review",
                target_id=str(review.id),
                result="success",
                detail=json.dumps(
                    {
                        "user_id": user.id,
                        "from_status": review.from_status,
                        "to_status": review.to_status,
                        "remark": review.remark,
                    },
                    ensure_ascii=False,
                ),
            )
        )
        db.commit()
        db.refresh(review)
        if approve:
            PartyNotifyAdapter.notify_political_status_approved(
                db,
                review_id=review.id,
                user_id=user.id,
                political_status=review.to_status,
            )
        return review

    @staticmethod
    def sync_from_party_profile(db: Session, user: User) -> bool:
        party = user.party
        target = PARTY_TYPE_TO_POLITICAL_STATUS.get(str(party.get("party_type") or ""))
        if not target or party.get("deleted_at"):
            return False
        if PartyPoliticalStatusService.effective_status(user) == target:
            return False
        user.political_status = target
        user.political_status_updated_at = local_now()
        db.add(user)
        return True
