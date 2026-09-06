import os

from sqlalchemy.orm import Session

from backend.app.ai.parser import ALLOWED_EXTENSIONS, is_allowed_extension
from backend.app.core.config import settings
from backend.app.core.storage import StorageService
from backend.app.models.file import KnowledgeFileVersion
from backend.app.repositories.file_repo import FileRepository
from backend.app.services.file_service import FileService


class KnowledgeVersionService:
    LIMIT = 20

    @classmethod
    def replace(cls, db: Session, item, upload, uploaded_by: int):
        if item.scope != "class":
            raise ValueError("仅班级文件支持版本管理")
        if not upload.filename or not is_allowed_extension(upload.filename):
            raise ValueError("不支持的文件类型")
        StorageService.validate_upload(
            upload,
            max_bytes=settings.DEFAULT_QUOTA_MB * 1024 * 1024,
            allowed_extensions=ALLOWED_EXTENSIONS,
        )
        history = KnowledgeFileVersion(
            file_id=item.id,
            version=item.version,
            stored_name=item.stored_name,
            original_name=item.original_name,
            mime_type=item.mime_type,
            size=item.size,
            uploaded_by=uploaded_by,
        )
        db.add(history)
        stored_name, mime_type, size = StorageService.save_file("class", item.owner_user_id, upload)
        item.stored_name, item.original_name, item.mime_type, item.size = stored_name, upload.filename, mime_type, size
        item.version += 1
        FileRepository.delete_chunks(db, item.id)
        db.commit()
        db.refresh(item)
        FileService.parse_file_sync(db, item, "class", item.owner_user_id)
        versions = FileRepository.list_versions(db, item.id)
        for old in versions[cls.LIMIT :]:
            StorageService.delete_file("class", item.owner_user_id, old.stored_name)
            db.delete(old)
        db.commit()
        return item
