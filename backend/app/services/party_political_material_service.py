from __future__ import annotations

import os
from typing import Any

from fastapi import UploadFile
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.database import local_now
from backend.app.core.errors import AppException
from backend.app.core.storage import StorageService
from backend.app.models.party import PoliticalLearningMaterial
from backend.app.models.user import User
from backend.app.services.party_knowledge_adapter import PartyKnowledgeAdapter
from backend.app.services.party_political_status_service import PartyPoliticalStatusService


VALID_ROLES = {
    "中共党员", "预备党员", "入党积极分子", "共青团员", "群众", "全体学生", "指定人员"
}
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}


class PartyPoliticalMaterialService:
    @staticmethod
    def _validate_targets(roles: list[str], target_ids: list[int]) -> None:
        if any(role not in VALID_ROLES for role in roles):
            raise AppException("POLITICAL_MATERIAL_TARGET_INVALID", "资料适用对象无效", 422)
        if len(target_ids) != len(set(target_ids)) or any(item <= 0 for item in target_ids):
            raise AppException("POLITICAL_MATERIAL_TARGET_INVALID", "指定用户 ID 无效", 422)
        if "指定人员" in roles and not target_ids:
            raise AppException("POLITICAL_MATERIAL_TARGET_INVALID", "指定人员资料必须提供名单", 422)

    @staticmethod
    def _serialize(item: PoliticalLearningMaterial) -> dict[str, Any]:
        return {
            "id": item.id, "title": item.title, "description": item.description,
            "applicable_roles": item.applicable_roles,
            "target_user_ids": item.target_user_ids,
            "attachments": item.attachments, "status": item.status,
            "created_by": item.created_by, "created_at": item.created_at,
            "updated_at": item.updated_at, "deleted_at": item.deleted_at,
        }

    @staticmethod
    def create(db: Session, values: dict[str, Any], created_by: int) -> PoliticalLearningMaterial:
        roles = values.pop("applicable_roles", [])
        target_ids = values.pop("target_user_ids", [])
        attachments = values.pop("attachments", [])
        PartyPoliticalMaterialService._validate_targets(roles, target_ids)
        item = PoliticalLearningMaterial(created_by=created_by, **values)
        item.applicable_roles = roles
        item.target_user_ids = target_ids
        item.attachments = attachments
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def get(db: Session, material_id: int) -> PoliticalLearningMaterial:
        item = db.query(PoliticalLearningMaterial).filter(
            PoliticalLearningMaterial.id == material_id,
            PoliticalLearningMaterial.deleted_at.is_(None),
        ).first()
        if not item:
            raise AppException("POLITICAL_MATERIAL_NOT_FOUND", "政治学习资料不存在", 404)
        return item

    @staticmethod
    def update(db: Session, material_id: int, values: dict[str, Any]) -> PoliticalLearningMaterial:
        item = PartyPoliticalMaterialService.get(db, material_id)
        roles = values.pop("applicable_roles", item.applicable_roles)
        target_ids = values.pop("target_user_ids", item.target_user_ids)
        PartyPoliticalMaterialService._validate_targets(roles, target_ids)
        for key, value in values.items():
            if key == "attachments":
                item.attachments = value
            else:
                setattr(item, key, value)
        item.applicable_roles = roles
        item.target_user_ids = target_ids
        item.updated_at = local_now()
        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def visible(db: Session, user: User) -> list[PoliticalLearningMaterial]:
        query = db.query(PoliticalLearningMaterial).filter(
            PoliticalLearningMaterial.deleted_at.is_(None)
        )
        if user.is_admin:
            return query.order_by(PoliticalLearningMaterial.created_at.desc()).all()
        query = query.filter(PoliticalLearningMaterial.status == "published")
        if user.is_teacher:
            return [
                item
                for item in query.order_by(PoliticalLearningMaterial.created_at.desc()).all()
                if "全体学生" in item.applicable_roles
            ]
        if not user.is_student:
            return []
        status = PartyPoliticalStatusService.effective_status(user)
        items = query.order_by(PoliticalLearningMaterial.created_at.desc()).all()
        return [
            item for item in items
            if ("全体学生" in item.applicable_roles
                or status in item.applicable_roles
                or ("指定人员" in item.applicable_roles and user.id in item.target_user_ids))
        ]

    @staticmethod
    def delete(db: Session, material_id: int) -> None:
        item = PartyPoliticalMaterialService.get(db, material_id)
        item.deleted_at = local_now()
        db.commit()

    @staticmethod
    def upload_attachment(db: Session, material_id: int, file: UploadFile) -> PoliticalLearningMaterial:
        item = PartyPoliticalMaterialService.get(db, material_id)
        name = os.path.basename(file.filename or "")
        ext = os.path.splitext(name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS or not name:
            raise AppException("POLITICAL_MATERIAL_FILE_INVALID", "附件仅支持 PDF、JPG、JPEG、PNG", 400)
        stored_name, mime_type, size = StorageService.save_file("political_materials", item.id, file)
        limit = settings.PARTY_MATERIAL_MAX_MB * 1024 * 1024
        if size <= 0 or size > limit:
            StorageService.delete_file("political_materials", item.id, stored_name)
            raise AppException("POLITICAL_MATERIAL_FILE_INVALID", f"单份资料不能超过 {settings.PARTY_MATERIAL_MAX_MB}MB", 400)
        attachment = {"original_name": name, "stored_name": stored_name, "file_id": stored_name, "mime_type": mime_type, "size": size, "uploaded_at": local_now().isoformat()}
        item.attachments = [*item.attachments, attachment]
        db.add(item)
        db.commit()
        db.refresh(item)
        if "指定人员" not in item.applicable_roles:
            try:
                PartyKnowledgeAdapter.ingest_political_material(db, item=item, attachment=attachment)
            except (FileNotFoundError, ValueError):
                pass
        return item

    @staticmethod
    def get_attachment_for_download(
        db: Session, material_id: int, file_id: str, user: User
    ) -> tuple[str, dict[str, Any]]:
        safe_file_id = os.path.basename(file_id)
        if not safe_file_id or safe_file_id != file_id:
            raise AppException("POLITICAL_MATERIAL_FILE_NOT_FOUND", "政治学习附件不存在", 404)

        item = PartyPoliticalMaterialService.get(db, material_id)
        if not user.is_admin:
            visible_ids = {
                material.id for material in PartyPoliticalMaterialService.visible(db, user)
            }
            if item.id not in visible_ids:
                raise AppException("POLITICAL_MATERIAL_FILE_NOT_FOUND", "政治学习附件不存在", 404)

        attachment = next(
            (
                value
                for value in item.attachments
                if isinstance(value, dict)
                and str(value.get("stored_name") or value.get("file_id") or "")
                == safe_file_id
            ),
            None,
        )
        if attachment is None:
            raise AppException("POLITICAL_MATERIAL_FILE_NOT_FOUND", "政治学习附件不存在", 404)

        path = StorageService.get_file_path("political_materials", item.id, safe_file_id)
        if not os.path.isfile(path):
            raise AppException("POLITICAL_MATERIAL_FILE_NOT_FOUND", "政治学习附件不存在", 404)
        return path, attachment
