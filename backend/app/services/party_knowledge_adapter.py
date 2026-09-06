from __future__ import annotations

import os
from typing import Any

from fastapi import UploadFile
from sqlalchemy.orm import Session
from starlette.datastructures import Headers

from backend.app.ai.parser import is_allowed_extension
from backend.app.core.storage import StorageService
from backend.app.models.file import KnowledgeFile
from backend.app.repositories.file_repo import FileRepository
from backend.app.services.file_service import FileService


PARTY_KNOWLEDGE_TAG_PREFIX = "party_activity"
PARTY_DEVELOPMENT_MATERIALS_ARE_SENSITIVE = True


class PartyKnowledgeAdapter:
    """仅把活动学习材料复制并解析到班级知识库。"""

    @staticmethod
    def ingest_activity_material(
        db: Session,
        *,
        activity,
        attachment: dict[str, Any],
    ) -> KnowledgeFile | None:
        stored_name = str(attachment.get("stored_name") or attachment.get("file_id") or "")
        original_name = str(attachment.get("original_name") or "")
        if not stored_name or not original_name:
            return None
        tag = f"{PARTY_KNOWLEDGE_TAG_PREFIX}:{activity.id}:{stored_name}"
        existing = (
            db.query(KnowledgeFile)
            .filter(
                KnowledgeFile.scope == "class",
                KnowledgeFile.tag == tag,
                KnowledgeFile.deleted_at.is_(None),
            )
            .first()
        )
        if existing:
            return existing

        source_path = StorageService.get_file_path(
            "party_activities", activity.id, stored_name
        )
        if not os.path.isfile(source_path):
            raise FileNotFoundError(f"党建活动学习材料不存在: {stored_name}")
        mime_type = str(attachment.get("mime_type") or "application/octet-stream")
        with open(source_path, "rb") as source:
            upload = UploadFile(
                file=source,
                filename=original_name,
                headers=Headers({"content-type": mime_type}),
            )
            if not is_allowed_extension(original_name):
                copied_name, copied_mime, copied_size = StorageService.save_file(
                    "class", activity.created_by, upload
                )
                knowledge = FileRepository.create(
                    db,
                    owner_user_id=activity.created_by,
                    scope="class",
                    original_name=original_name,
                    stored_name=copied_name,
                    mime_type=copied_mime,
                    size=copied_size,
                    tag=tag,
                )
                FileRepository.update_parse_status(
                    db, knowledge, "failed", "该学习材料格式不支持文本解析"
                )
                db.refresh(knowledge)
                return knowledge
            result = FileService.upload_and_parse(
                db,
                user_id=activity.created_by,
                scope="class",
                file=upload,
                tag=tag,
            )
        return db.get(KnowledgeFile, result["id"])

    @staticmethod
    def ingest_development_material(*args, **kwargs) -> None:
        """党员发展材料属涉敏数据，禁止进入知识库。"""
        return None

    @staticmethod
    def ingest_political_material(
        db: Session,
        *,
        item,
        attachment: dict[str, Any],
    ) -> KnowledgeFile | None:
        """将非指定人员的政治学习资料复制到班级知识库并解析。"""
        stored_name = str(
            attachment.get("stored_name") or attachment.get("file_id") or ""
        )
        original_name = str(attachment.get("original_name") or "")
        if not stored_name or not original_name:
            return None
        tag = f"political_material:{item.id}:{stored_name}"
        existing = (
            db.query(KnowledgeFile)
            .filter(
                KnowledgeFile.scope == "class",
                KnowledgeFile.tag == tag,
                KnowledgeFile.deleted_at.is_(None),
            )
            .first()
        )
        if existing:
            return existing
        source_path = StorageService.get_file_path(
            "political_materials", item.id, stored_name
        )
        if not os.path.isfile(source_path):
            raise FileNotFoundError(f"政治学习资料不存在: {stored_name}")
        mime_type = str(attachment.get("mime_type") or "application/octet-stream")
        with open(source_path, "rb") as source:
            upload = UploadFile(
                file=source,
                filename=original_name,
                headers=Headers({"content-type": mime_type}),
            )
            result = FileService.upload_and_parse(
                db,
                user_id=item.created_by,
                scope="class",
                file=upload,
                tag=tag,
            )
        return db.get(KnowledgeFile, result["id"])


ingest_party_activity_material = PartyKnowledgeAdapter.ingest_activity_material
sync_party_activity_material = PartyKnowledgeAdapter.ingest_activity_material
ingest_party_development_material = PartyKnowledgeAdapter.ingest_development_material
