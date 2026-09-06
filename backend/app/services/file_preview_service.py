"""Shared, defensive file preview implementation used by all attachment domains."""
import hashlib
import html
import logging
import mimetypes
import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from backend.app.core.config import settings
from backend.app.core.storage import StorageService

logger = logging.getLogger(__name__)
TEXT_EXTENSIONS = {".txt", ".csv", ".json", ".log", ".xml", ".yaml", ".yml", ".toml", ".ini", ".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".go", ".rs", ".rb", ".php", ".html", ".css", ".sh"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
OFFICE_EXTENSIONS = {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"}
FALLBACK_MESSAGE = "暂不支持预览，请下载查看"


def _safe_markdown(value: str) -> str:
    escaped = html.escape(value)
    escaped = re.sub(r"^### (.+)$", r"<h3>\1</h3>", escaped, flags=re.MULTILINE)
    escaped = re.sub(r"^## (.+)$", r"<h2>\1</h2>", escaped, flags=re.MULTILINE)
    return re.sub(r"^# (.+)$", r"<h1>\1</h1>", escaped, flags=re.MULTILINE)


class FilePreviewService:
    INLINE_EXTENSIONS = IMAGE_EXTENSIONS | {".pdf"}
    OFFICE_EXTENSIONS = OFFICE_EXTENSIONS
    _global_semaphore = threading.BoundedSemaphore(max(1, settings.PREVIEW_OFFICE_CONCURRENCY))
    _locks: dict[str, threading.Lock] = {}
    _locks_guard = threading.Lock()

    @staticmethod
    def _unsupported() -> dict:
        return {"supported": False, "preview_url": None, "content": None, "message": FALLBACK_MESSAGE, "format": None}

    @staticmethod
    def cache_path(scope: str, user_id: int, stored_name: str, size: int, version: int) -> Path:
        key = hashlib.sha256(f"{stored_name}{size}{version}".encode()).hexdigest()
        return Path(settings.STORAGE_PATH) / "preview_cache" / scope / str(user_id) / f"{key}.pdf"

    @classmethod
    def _convert_office(cls, path: str, scope: str, user_id: int, stored_name: str, size: int, version: int) -> str | None:
        if not settings.PREVIEW_OFFICE_ENABLED or size > settings.PREVIEW_OFFICE_MAX_MB * 1024 * 1024:
            return None
        target = cls.cache_path(scope, user_id, stored_name, size, version)
        if target.is_file():
            return str(target)
        with cls._locks_guard:
            lock = cls._locks.setdefault(str(target), threading.Lock())
        with lock, cls._global_semaphore:
            if target.is_file():
                return str(target)
            executable = shutil.which("soffice") or shutil.which("libreoffice")
            if not executable:
                logger.info("Office preview unavailable: soffice is not installed")
                return None
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="preview-office-") as temp_dir:
                profile = Path(temp_dir) / "profile"
                out_dir = Path(temp_dir) / "out"
                out_dir.mkdir()
                command = [executable, "--headless", "--norestore", f"-env:UserInstallation={profile.as_uri()}",
                           "--convert-to", "pdf", "--outdir", str(out_dir), path]
                for attempt in range(2):
                    try:
                        subprocess.run(command, capture_output=True, check=True,
                                       timeout=settings.PREVIEW_OFFICE_TIMEOUT_SECONDS)
                        output = out_dir / (Path(path).stem + ".pdf")
                        if output.is_file():
                            shutil.copyfile(output, target)
                            return str(target)
                    except (subprocess.SubprocessError, OSError) as exc:
                        logger.warning("Office preview failed (attempt %d): %s", attempt + 1, exc)
            return None

    @classmethod
    def preview(cls, *, path: str, original_name: str, stored_name: str, mime_type: str,
                size: int, scope: str, user_id: int, version: int = 1) -> dict:
        base = {"original_name": original_name, "size": size, "supported": True,
                "preview_url": None, "content": None, "message": None, "format": None}
        try:
            if not os.path.isfile(path):
                return cls._unsupported()
            ext = Path(original_name).suffix.lower()
            if ext in IMAGE_EXTENSIONS or ext == ".pdf":
                return {**base, "format": "inline", "mime_type": mimetypes.guess_type(original_name)[0] or mime_type}
            if ext in TEXT_EXTENSIONS or ext in {".md", ".markdown"}:
                if size > settings.PREVIEW_OFFICE_MAX_MB * 1024 * 1024:
                    return cls._unsupported()
                raw = Path(path).read_text(encoding="utf-8", errors="replace")[:2_000_000]
                content = _safe_markdown(raw) if ext in {".md", ".markdown"} else f"<pre>{html.escape(raw)}</pre>"
                return {**base, "format": "html", "content": content, "mime_type": "text/html"}
            if ext in OFFICE_EXTENSIONS:
                cached = cls._convert_office(path, scope, user_id, stored_name, size, version)
                if cached:
                    return {**base, "format": "inline", "preview_url": cached, "mime_type": "application/pdf"}
        except Exception:
            logger.exception("Preview failed for %s", original_name)
        return cls._unsupported()


def preview_file(scope: str, user_id: int, stored_name: str, original_name: str, size: int, version: int = 1) -> dict:
    """Compatibility entry point for attachment services."""
    path = StorageService.get_file_path(scope, user_id, stored_name)
    return FilePreviewService.preview(path=path, original_name=original_name, stored_name=stored_name,
                                      mime_type=mimetypes.guess_type(original_name)[0] or "application/octet-stream",
                                      size=size, scope=scope, user_id=user_id, version=version)
