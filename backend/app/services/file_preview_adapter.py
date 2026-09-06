import os
from pathlib import Path

from sqlalchemy.orm import Session

from backend.app.core.storage import StorageService
from backend.app.repositories.file_repo import FileRepository
from backend.app.services.file_preview_service import FilePreviewService


class FilePreviewAdapter:
    @staticmethod
    def preview(db: Session, file_id: int, user_id: int, scope: str) -> dict:
        item = FileRepository.get_by_id(db, file_id)
        if not item or item.scope != scope or (scope == "personal" and item.owner_user_id != user_id):
            raise ValueError("文件不存在")
        path = StorageService.get_file_path(item.scope, item.owner_user_id, item.stored_name)
        if not os.path.exists(path):
            raise ValueError("文件不存在")
        result = FilePreviewService.preview(
            path=path, original_name=item.original_name, stored_name=item.stored_name,
            mime_type=item.mime_type, size=item.size, scope=item.scope,
            user_id=item.owner_user_id, version=item.version,
        )
        if result.get("format") == "inline":
            result["preview_url"] = f"files/{item.id}/preview/raw"
        return result

    @staticmethod
    def raw_path(db: Session, file_id: int, user_id: int, scope: str) -> tuple[str, str]:
        item = FileRepository.get_by_id(db, file_id)
        if not item or item.scope != scope or (scope == "personal" and item.owner_user_id != user_id):
            raise ValueError("文件不存在")
        original = StorageService.get_file_path(item.scope, item.owner_user_id, item.stored_name)
        ext = Path(item.original_name).suffix.lower()
        if ext in FilePreviewService.OFFICE_EXTENSIONS:
            path = FilePreviewService.cache_path(item.scope, item.owner_user_id, item.stored_name, item.size, item.version)
            if path.is_file():
                return str(path), "application/pdf"
        if ext in FilePreviewService.INLINE_EXTENSIONS and os.path.isfile(original):
            return original, item.mime_type
        raise ValueError("文件不存在")
