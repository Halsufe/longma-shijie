import os
import uuid
import shutil
import logging
import re
from pathlib import Path
from urllib.parse import quote

import httpx

from fastapi import UploadFile

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

_TEXT_EXTENSIONS = frozenset({
    ".txt", ".md", ".markdown", ".csv", ".json", ".log", ".xml",
    ".yaml", ".yml", ".toml", ".ini", ".py", ".js", ".ts", ".java",
    ".c", ".cpp", ".h", ".go", ".rs", ".rb", ".php", ".html", ".css",
    ".sh",
})
_BINARY_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    ".pdf": (b"%PDF-",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".gif": (b"GIF87a", b"GIF89a"),
    ".bmp": (b"BM",),
    ".doc": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
    ".xls": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
    ".ppt": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
    ".docx": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
    ".xlsx": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
    ".pptx": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
}
_KNOWN_BINARY_PREFIXES = tuple(
    dict.fromkeys(
        signature
        for signatures in _BINARY_SIGNATURES.values()
        for signature in signatures
    )
) + (b"MZ", b"\x7fELF")


class StorageService:
    """文件存储抽象层：本地开发或 Supabase Storage 生产后端。"""

    @staticmethod
    def _remote_enabled() -> bool:
        return settings.STORAGE_BACKEND.lower() == "supabase"

    @staticmethod
    def _object_key(scope: str, user_id: int, stored_name: str) -> str:
        StorageService._validate_path_part(scope, "存储 scope")
        StorageService._validate_path_part(str(user_id), "存储所有者")
        StorageService._validate_path_part(stored_name, "文件名")
        return f"{scope}/{user_id}/{stored_name}"

    @staticmethod
    def _remote_url(path: str = "") -> str:
        base = settings.SUPABASE_URL.rstrip("/")
        bucket = quote(settings.SUPABASE_STORAGE_BUCKET, safe="")
        return f"{base}/storage/v1/object/{bucket}/{path}".rstrip("/")

    @staticmethod
    def _remote_remove_url() -> str:
        base = settings.SUPABASE_URL.rstrip("/")
        bucket = quote(settings.SUPABASE_STORAGE_BUCKET, safe="")
        return f"{base}/storage/v1/object/remove/{bucket}"

    @staticmethod
    def _remote_list_url() -> str:
        base = settings.SUPABASE_URL.rstrip("/")
        bucket = quote(settings.SUPABASE_STORAGE_BUCKET, safe="")
        return f"{base}/storage/v1/object/list/{bucket}"

    @staticmethod
    def _remote_headers() -> dict[str, str]:
        key = settings.SUPABASE_SERVICE_ROLE_KEY
        return {"Authorization": f"Bearer {key}", "apikey": key}

    @staticmethod
    def _ensure_dir(path: str) -> None:
        os.makedirs(path, exist_ok=True)

    @staticmethod
    def get_storage_dir(scope: str, user_id: int) -> str:
        """获取存储目录: storage/{scope}/{user_id}/"""
        if not StorageService._SCOPE_RE.fullmatch(scope):
            raise ValueError("非法存储 scope")
        if not isinstance(user_id, int) or user_id < 0:
            raise ValueError("非法存储所有者")
        path = os.path.join(settings.STORAGE_PATH, scope, str(user_id))
        StorageService._ensure_dir(path)
        return path

    @staticmethod
    def save_file(scope: str, user_id: int, file: UploadFile) -> tuple[str, str, int]:
        """
        保存上传文件
        返回: (stored_name, mime_type, size)
        """
        ext = os.path.splitext(file.filename or "")[1].lower()
        stored_name = f"{uuid.uuid4().hex}{ext}"
        if StorageService._remote_enabled():
            data = file.file.read()
            size = len(data)
            response = httpx.post(
                StorageService._remote_url(StorageService._object_key(scope, user_id, stored_name)),
                headers={**StorageService._remote_headers(), "Content-Type": file.content_type or "application/octet-stream", "x-upsert": "true"},
                content=data,
                timeout=120,
            )
            response.raise_for_status()
        else:
            storage_dir = StorageService.get_storage_dir(scope, user_id)
            file_path = os.path.join(storage_dir, stored_name)
            size = 0
            with open(file_path, "wb") as f:
                while True:
                    chunk = file.file.read(1024 * 1024)  # 1MB chunks
                    if not chunk:
                        break
                    f.write(chunk)
                    size += len(chunk)

        mime_type = file.content_type or "application/octet-stream"
        logger.info("File saved: %s -> %s (%d bytes)", file.filename, stored_name, size)
        return stored_name, mime_type, size

    @staticmethod
    def validate_upload(
        file: UploadFile,
        *,
        max_bytes: int | None = None,
        allowed_extensions: set[str] | frozenset[str] | None = None,
        check_signature: bool = True,
    ) -> int:
        """Validate an upload before persistence and leave its stream rewound."""
        name = file.filename or ""
        if not name:
            raise ValueError("file name is required")
        ext = os.path.splitext(name)[1].lower()
        if allowed_extensions is not None and ext not in allowed_extensions:
            raise ValueError("file extension is not allowed")
        file.file.seek(0, os.SEEK_END)
        size = file.file.tell()
        file.file.seek(0)
        if size <= 0:
            raise ValueError("file cannot be empty")
        if max_bytes is not None and size > max_bytes:
            raise ValueError("file exceeds the size limit")
        if check_signature:
            header = file.file.read(4096)
            file.file.seek(0)
            signatures = _BINARY_SIGNATURES.get(ext)
            if ext == ".pdf":
                matched = b"%PDF-" in header[:1024]
            elif ext == ".webp":
                matched = (
                    len(header) >= 12
                    and header.startswith(b"RIFF")
                    and header[8:12] == b"WEBP"
                )
            elif signatures:
                matched = header.startswith(signatures)
            elif ext in _TEXT_EXTENSIONS:
                matched = b"\x00" not in header and not header.startswith(
                    _KNOWN_BINARY_PREFIXES
                )
            else:
                matched = True
            if not matched:
                raise ValueError("file signature does not match its extension")
        return size

    @staticmethod
    def save_bytes(scope: str, user_id: int, data: bytes, ext: str = "") -> tuple[str, int]:
        """保存字节数据"""
        stored_name = f"{uuid.uuid4().hex}{ext}"
        if StorageService._remote_enabled():
            response = httpx.post(
                StorageService._remote_url(StorageService._object_key(scope, user_id, stored_name)),
                headers={**StorageService._remote_headers(), "x-upsert": "true"}, content=data, timeout=120,
            )
            response.raise_for_status()
        else:
            storage_dir = StorageService.get_storage_dir(scope, user_id)
            file_path = os.path.join(storage_dir, stored_name)
            with open(file_path, "wb") as f:
                f.write(data)
        return stored_name, len(data)

    @staticmethod
    def get_file_path(scope: str, user_id: int, stored_name: str) -> str:
        StorageService._validate_path_part(stored_name, "文件名")
        if not StorageService._remote_enabled():
            return os.path.join(StorageService.get_storage_dir(scope, user_id), stored_name)
        cache_dir = os.path.join(settings.STORAGE_PATH, ".cache", scope, str(user_id))
        StorageService._ensure_dir(cache_dir)
        cache_path = os.path.join(cache_dir, stored_name)
        if not os.path.isfile(cache_path):
            response = httpx.get(
                StorageService._remote_url(StorageService._object_key(scope, user_id, stored_name)),
                headers=StorageService._remote_headers(), timeout=120,
            )
            if response.status_code == 404:
                return cache_path
            response.raise_for_status()
            with open(cache_path, "wb") as target:
                target.write(response.content)
        return cache_path

    @staticmethod
    def delete_file(scope: str, user_id: int, stored_name: str) -> bool:
        if StorageService._remote_enabled():
            response = httpx.post(
                StorageService._remote_remove_url(),
                headers={**StorageService._remote_headers(), "Content-Type": "application/json"},
                json={"prefixes": [StorageService._object_key(scope, user_id, stored_name)]},
                timeout=60,
            )
            response.raise_for_status()
            cache_path = os.path.join(settings.STORAGE_PATH, ".cache", scope, str(user_id), stored_name)
            try:
                os.remove(cache_path)
            except OSError:
                pass
            return True
        file_path = StorageService.get_file_path(scope, user_id, stored_name)
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info("File deleted: %s", stored_name)
                return True
        except OSError as e:
            logger.error("Failed to delete file %s: %s", stored_name, e)
        return False

    @staticmethod
    def file_exists(scope: str, user_id: int, stored_name: str) -> bool:
        if not StorageService._remote_enabled():
            return os.path.exists(StorageService.get_file_path(scope, user_id, stored_name))
        response = httpx.head(
            StorageService._remote_url(StorageService._object_key(scope, user_id, stored_name)),
            headers=StorageService._remote_headers(), timeout=30,
        )
        return response.is_success

    @staticmethod
    def get_user_usage(user_id: int) -> int:
        """获取用户个人知识库已用空间（字节）"""
        if StorageService._remote_enabled():
            return StorageService._remote_usage(f"personal/{user_id}")
        personal_dir = os.path.join(settings.STORAGE_PATH, "personal", str(user_id))
        if not os.path.exists(personal_dir):
            return 0
        total = 0
        for dirpath, _, filenames in os.walk(personal_dir):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.isfile(fp):
                    total += os.path.getsize(fp)
        return total

    @staticmethod
    def get_class_usage() -> int:
        """获取班级知识库已用空间"""
        if StorageService._remote_enabled():
            return StorageService._remote_usage("class")
        class_dir = os.path.join(settings.STORAGE_PATH, "class")
        if not os.path.exists(class_dir):
            return 0
        total = 0
        for dirpath, _, filenames in os.walk(class_dir):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.isfile(fp):
                    total += os.path.getsize(fp)
        return total

    @staticmethod
    def _remote_usage(prefix: str) -> int:
        response = httpx.post(
            StorageService._remote_list_url(),
            headers={**StorageService._remote_headers(), "Content-Type": "application/json"},
            json={"prefix": prefix, "limit": 1000, "offset": 0},
            timeout=60,
        )
        response.raise_for_status()
        return sum(int(item.get("metadata", {}).get("size", 0) or item.get("size", 0) or 0) for item in response.json())
    _SCOPE_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
    COMMON_SCOPES = frozenset({"personal", "class", "assignment", "submission", "chat"})

    @staticmethod
    def _validate_path_part(value: str, label: str) -> str:
        if not value or value in {".", ".."} or "/" in value or "\\" in value:
            raise ValueError(f"非法{label}")
        return value
