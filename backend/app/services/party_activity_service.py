import os
from datetime import datetime
from typing import Any

from fastapi import UploadFile
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.database import CST, local_now
from backend.app.core.errors import AppException
from backend.app.core.pagination import normalize_page, normalize_page_size
from backend.app.core.storage import StorageService
from backend.app.models.party import PartyActivity
from backend.app.models.user import User, UserRole
from backend.app.repositories.party_repo import PartyRepository
from backend.app.services.party_knowledge_adapter import PartyKnowledgeAdapter
from backend.app.services.party_notify_adapter import PartyNotifyAdapter
from backend.app.services.party_target_roles import matches_target_role


ACTIVITY_STATUSES = ("draft", "published", "ongoing", "finished", "archived")
LOCKED_AFTER_REGISTRATION = {
    "registration_deadline",
    "target_roles",
    "target_member_ids",
    "max_participants",
}
ACTIVITY_STORAGE_SCOPE = "party_activities"
ALLOWED_ACTIVITY_FILES = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


def _comparable(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(CST).replace(tzinfo=None)


class PartyActivityService:
    @staticmethod
    def serialize(activity: PartyActivity) -> dict[str, Any]:
        return {
            "id": activity.id,
            "title": activity.title,
            "category": activity.category,
            "content": activity.content,
            "location": activity.location,
            "start_at": activity.start_at,
            "end_at": activity.end_at,
            "registration_deadline": activity.registration_deadline,
            "target_roles": activity.target_roles,
            "target_member_ids": activity.target_member_ids,
            "target_member_ids_json": activity.target_member_ids,
            "max_participants": activity.max_participants,
            "materials": activity.materials,
            "materials_json": activity.materials,
            "summary": activity.summary,
            "summary_attachments": activity.summary_attachments,
            "summary_attachments_json": activity.summary_attachments,
            "status": activity.status,
            "created_by": activity.created_by,
            "created_at": activity.created_at,
            "updated_at": activity.updated_at,
            "deleted_at": activity.deleted_at,
        }

    @staticmethod
    def serialize_for_user(db: Session, activity: PartyActivity, user: User) -> dict[str, Any]:
        result = PartyActivityService.serialize(activity)
        participant = PartyRepository.get_participant(db, activity.id, user.id)
        if participant is None:
            result.update({"participant": None, "my_participation": None})
            return result
        from backend.app.services.party_registration_service import (
            PartyRegistrationService,
        )

        serialized = PartyRegistrationService.serialize(participant)
        result.update({"participant": serialized, "my_participation": serialized})
        return result

    @staticmethod
    def get_or_404(db: Session, activity_id: int) -> PartyActivity:
        activity = PartyRepository.get_activity(db, activity_id)
        if not activity:
            raise AppException("PARTY_ACTIVITY_NOT_FOUND", "党建活动不存在", 404)
        return activity

    @staticmethod
    def _validate_values(values: dict[str, Any]) -> None:
        start_at = values.get("start_at")
        end_at = values.get("end_at")
        if start_at and end_at and _comparable(end_at) <= _comparable(start_at):
            raise AppException(
                "PARTY_ACTIVITY_INVALID", "活动结束时间必须晚于开始时间", 422
            )
        target_roles = values.get("target_roles")
        target_member_ids = values.get("target_member_ids") or []
        if target_roles == "指定人员" and not target_member_ids:
            raise AppException(
                "PARTY_ACTIVITY_INVALID", "参加对象为指定人员时必须提供指定人员名单", 422
            )
        if len(target_member_ids) != len(set(target_member_ids)) or any(
            not isinstance(user_id, int) or user_id <= 0 for user_id in target_member_ids
        ):
            raise AppException(
                "PARTY_ACTIVITY_INVALID", "指定人员名单必须是无重复的正整数用户 ID", 422
            )

    @staticmethod
    def _validate_publish(activity: PartyActivity) -> None:
        deadline = activity.registration_deadline
        if deadline is not None and _comparable(deadline) >= _comparable(activity.start_at):
            raise AppException(
                "PARTY_ACTIVITY_DEADLINE_INVALID", "报名截止时间必须早于活动开始时间", 422
            )

    @staticmethod
    def create(db: Session, values: dict[str, Any], created_by: int) -> PartyActivity:
        PartyActivityService._validate_values(values)
        target_ids = values.pop("target_member_ids", [])
        materials = values.pop("materials", [])
        activity = PartyRepository.create_activity(
            db, **values, status="draft", created_by=created_by
        )
        activity.target_member_ids = target_ids
        activity.materials = materials
        db.commit()
        db.refresh(activity)
        return activity

    @staticmethod
    def update(
        db: Session, activity_id: int, values: dict[str, Any]
    ) -> PartyActivity:
        activity = PartyActivityService.get_or_404(db, activity_id)
        if activity.status == "archived":
            raise AppException(
                "PARTY_ACTIVITY_ARCHIVED", "已归档活动只允许查看", 409
            )
        if activity.status != "draft" and LOCKED_AFTER_REGISTRATION.intersection(values):
            raise AppException(
                "PARTY_ACTIVITY_REGISTRATION_LOCKED",
                "报名开始后不可修改报名截止、参加对象、指定人员名单或名额",
                409,
            )
        merged = PartyActivityService.serialize(activity)
        merged.update(values)
        PartyActivityService._validate_values(merged)
        for key, value in values.items():
            if key == "target_member_ids":
                activity.target_member_ids = value
            elif key == "materials":
                activity.materials = value
            elif key == "summary_attachments":
                activity.summary_attachments = value
            else:
                setattr(activity, key, value)
        db.add(activity)
        db.commit()
        db.refresh(activity)
        return activity

    @staticmethod
    def transition(
        db: Session, activity_id: int, target_status: str
    ) -> PartyActivity:
        activity = PartyActivityService.get_or_404(db, activity_id)
        try:
            expected = ACTIVITY_STATUSES[ACTIVITY_STATUSES.index(activity.status) + 1]
        except (ValueError, IndexError):
            expected = None
        if target_status != expected:
            raise AppException(
                "PARTY_ACTIVITY_STATUS_INVALID",
                f"活动状态只能逐级流转，当前状态 {activity.status} 的下一状态为 {expected or '无'}",
                409,
            )
        if target_status == "published":
            PartyActivityService._validate_publish(activity)
        activity.status = target_status
        db.add(activity)
        db.commit()
        db.refresh(activity)
        if target_status == "published":
            PartyActivityService._notify_published(db, activity)
        return activity

    @staticmethod
    def update_summary(
        db: Session, activity_id: int, values: dict[str, Any]
    ) -> PartyActivity:
        activity = PartyActivityService.get_or_404(db, activity_id)
        if activity.status == "archived":
            raise AppException("PARTY_ACTIVITY_ARCHIVED", "已归档活动只允许查看", 409)
        if activity.status not in {"ongoing", "finished"}:
            raise AppException(
                "PARTY_ACTIVITY_SUMMARY_INVALID", "仅进行中或已结束活动可填写总结", 409
            )
        if values.get("archive") and activity.status != "finished":
            raise AppException(
                "PARTY_ACTIVITY_STATUS_INVALID",
                "活动必须先从进行中流转为已结束，才能保存总结并归档",
                409,
            )
        activity.summary = values["summary"]
        activity.summary_attachments = values.get("summary_attachments", [])
        db.add(activity)
        db.commit()
        db.refresh(activity)
        if values.get("archive"):
            return PartyActivityService.transition(db, activity.id, "archived")
        return activity

    @staticmethod
    def delete(db: Session, activity_id: int) -> PartyActivity:
        activity = PartyActivityService.get_or_404(db, activity_id)
        if activity.status != "archived":
            raise AppException(
                "PARTY_ACTIVITY_DELETE_INVALID", "仅已归档活动允许删除", 409
            )
        PartyRepository.soft_delete_activity(db, activity)
        db.commit()
        db.refresh(activity)
        return activity

    @staticmethod
    def is_visible(activity: PartyActivity, user: User) -> bool:
        if user.is_admin:
            return True
        if activity.status == "draft" or user.role == UserRole.ALUMNI.value:
            return False
        if activity.target_roles == "指定人员":
            return user.id in activity.target_member_ids
        return matches_target_role(user, activity.target_roles)

    @staticmethod
    def list_visible(
        db: Session,
        user: User,
        *,
        status: str | None,
        category: str | None,
        year: int | None,
        page: int,
        page_size: int,
    ) -> tuple[list[PartyActivity], int, int, int]:
        normalized_page = normalize_page(page)
        normalized_size = normalize_page_size(page_size)
        activities = PartyRepository.query_activities(
            db, status=status, category=category, year=year
        )
        visible = [item for item in activities if PartyActivityService.is_visible(item, user)]
        total = len(visible)
        start = (normalized_page - 1) * normalized_size
        return (
            visible[start : start + normalized_size],
            total,
            normalized_page,
            normalized_size,
        )

    @staticmethod
    def visible_or_404(db: Session, activity_id: int, user: User) -> PartyActivity:
        activity = PartyActivityService.get_or_404(db, activity_id)
        if not PartyActivityService.is_visible(activity, user):
            raise AppException("PARTY_ACTIVITY_NOT_FOUND", "党建活动不存在", 404)
        return activity

    @staticmethod
    def upload_material(
        db: Session, activity_id: int, file: UploadFile
    ) -> PartyActivity:
        activity = PartyActivityService.get_or_404(db, activity_id)
        if activity.status == "archived":
            raise AppException("PARTY_ACTIVITY_ARCHIVED", "已归档活动只允许查看", 409)
        original_name = os.path.basename(file.filename or "")
        extension = os.path.splitext(original_name)[1].lower()
        mime_type = (file.content_type or "").lower()
        if not original_name or ALLOWED_ACTIVITY_FILES.get(extension) != mime_type:
            raise AppException(
                "PARTY_ACTIVITY_FILE_INVALID", "活动材料仅支持 PDF、JPG、JPEG、PNG 格式", 400
            )
        stored_name, stored_mime, size = StorageService.save_file(
            ACTIVITY_STORAGE_SCOPE, activity.id, file
        )
        max_size = settings.PARTY_MATERIAL_MAX_MB * 1024 * 1024
        if size <= 0 or size > max_size:
            StorageService.delete_file(ACTIVITY_STORAGE_SCOPE, activity.id, stored_name)
            message = "活动材料不能为空" if size <= 0 else f"单份活动材料不能超过 {settings.PARTY_MATERIAL_MAX_MB}MB"
            raise AppException("PARTY_ACTIVITY_FILE_INVALID", message, 400)
        attachment = {
            "original_name": original_name,
            "file_id": stored_name,
            "stored_name": stored_name,
            "mime_type": stored_mime,
            "size": size,
            "uploaded_at": local_now().isoformat(),
        }
        activity.materials = [*activity.materials, attachment]
        db.add(activity)
        db.commit()
        db.refresh(activity)
        PartyKnowledgeAdapter.ingest_activity_material(
            db, activity=activity, attachment=attachment
        )
        return activity

    @staticmethod
    def _target_users(db: Session, activity: PartyActivity) -> list[User]:
        users = (
            db.query(User)
            .filter(User.status == "active", User.deleted_at.is_(None))
            .all()
        )
        return [user for user in users if not user.is_admin and PartyActivityService.is_visible(activity, user)]

    @staticmethod
    def _notify_published(db: Session, activity: PartyActivity) -> None:
        targets = PartyActivityService._target_users(db, activity)
        target_ids = [user.id for user in targets]
        PartyNotifyAdapter.notify_party_activity_published(
            db,
            activity=activity,
            target_user_ids=target_ids,
        )
