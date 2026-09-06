import os
from datetime import datetime, timezone
from typing import Any

from fastapi import UploadFile

from backend.app.core.config import settings
from backend.app.core.storage import StorageService


ACHIEVEMENT_FILE_SCOPE = "achievements"
ALLOWED_ACHIEVEMENT_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
ALLOWED_ACHIEVEMENT_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
}


class AchievementFileService:
    @staticmethod
    def upload(user_id: int, file: UploadFile) -> dict[str, Any]:
        original_name = os.path.basename(file.filename or "")
        extension = os.path.splitext(original_name)[1].lower()
        mime_type = (file.content_type or "").lower()
        if extension not in ALLOWED_ACHIEVEMENT_EXTENSIONS or mime_type not in ALLOWED_ACHIEVEMENT_MIME_TYPES:
            raise ValueError("证明材料仅支持 PDF、JPG、JPEG、PNG 格式")

        stored_name, stored_mime, size = StorageService.save_file(
            ACHIEVEMENT_FILE_SCOPE, user_id, file
        )
        max_size = settings.ACHIEVEMENT_FILE_MAX_MB * 1024 * 1024
        if size <= 0:
            StorageService.delete_file(ACHIEVEMENT_FILE_SCOPE, user_id, stored_name)
            raise ValueError("证明材料不能为空")
        if size > max_size:
            StorageService.delete_file(ACHIEVEMENT_FILE_SCOPE, user_id, stored_name)
            raise ValueError(f"单份证明材料不能超过 {settings.ACHIEVEMENT_FILE_MAX_MB}MB")

        return {
            "id": stored_name,
            "name": original_name,
            "path": stored_name,
            "stored_name": stored_name,
            "size": size,
            "mime": stored_mime,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def normalize_proofs(proofs: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        seen: set[str] = set()
        for proof in proofs or []:
            if not isinstance(proof, dict):
                raise ValueError("证明材料记录格式无效")
            stored_name = os.path.basename(
                str(
                    proof.get("stored_name")
                    or proof.get("path")
                    or proof.get("id")
                    or ""
                )
            )
            if not stored_name:
                raise ValueError("证明材料标识无效")
            if stored_name in seen:
                continue
            seen.add(stored_name)
            try:
                size = int(proof.get("size") or 0)
            except (TypeError, ValueError) as exc:
                raise ValueError("证明材料大小无效") from exc
            normalized.append(
                {
                    "id": stored_name,
                    "name": str(proof.get("name") or stored_name),
                    "path": stored_name,
                    "stored_name": stored_name,
                    "size": size,
                    "mime": str(proof.get("mime") or "application/octet-stream"),
                    "uploaded_at": str(proof.get("uploaded_at") or ""),
                    "description": str(proof.get("description") or ""),
                }
            )
        return normalized

    @staticmethod
    def validate_owned(user_id: int, proofs: list[dict[str, Any]]) -> None:
        for proof in proofs:
            if not StorageService.file_exists(
                ACHIEVEMENT_FILE_SCOPE, user_id, proof["stored_name"]
            ):
                raise ValueError(f"证明材料不存在或无权访问：{proof['name']}")

    @staticmethod
    def get_path(user_id: int, stored_name: str) -> str:
        safe_name = os.path.basename(stored_name)
        path = StorageService.get_file_path(ACHIEVEMENT_FILE_SCOPE, user_id, safe_name)
        if not os.path.isfile(path):
            raise ValueError("证明材料不存在")
        return path

    @staticmethod
    def delete(user_id: int, stored_name: str) -> bool:
        return StorageService.delete_file(
            ACHIEVEMENT_FILE_SCOPE, user_id, os.path.basename(stored_name)
        )

    @staticmethod
    def delete_removed(
        user_id: int,
        previous: list[dict[str, Any]],
        current: list[dict[str, Any]],
    ) -> None:
        current_ids = {
            str(item.get("stored_name") or item.get("id") or "") for item in current
        }
        for proof in previous:
            stored_name = str(proof.get("stored_name") or proof.get("id") or "")
            if stored_name and stored_name not in current_ids:
                AchievementFileService.delete(user_id, stored_name)
