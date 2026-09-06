import io
import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.config import settings
from backend.app.core.database import Base
from backend.app.core.storage import StorageService
from backend.app.models.runtime_config import RuntimeConfig
from backend.app.models.user import User  # noqa: F401 - registers FK target
from backend.app.services.file_preview_service import FilePreviewService, preview_file
from backend.app.services.runtime_config_service import RuntimeConfigService
from backend.app.workers.file_cleanup import cleanup_preview_cache


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_storage_rejects_path_traversal_and_supports_shared_scopes(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_PATH", str(tmp_path))
    for scope in StorageService.COMMON_SCOPES:
        stored, size = StorageService.save_bytes(scope, 1, b"hello", ".txt")
        assert size == 5
        assert Path(StorageService.get_file_path(scope, 1, stored)).read_bytes() == b"hello"
    with pytest.raises(ValueError):
        StorageService.get_file_path("personal", 1, "../secret")
    with pytest.raises(ValueError):
        StorageService.get_storage_dir("../personal", 1)


def test_storage_validates_binary_and_disguised_text_file_headers():
    valid_pdf = UploadFile(filename="valid.pdf", file=io.BytesIO(b"%PDF-1.7\n"))
    assert StorageService.validate_upload(
        valid_pdf, max_bytes=1024, allowed_extensions={".pdf"}
    ) == 9
    assert valid_pdf.file.tell() == 0

    fake_pdf = UploadFile(filename="fake.pdf", file=io.BytesIO(b"plain text"))
    with pytest.raises(ValueError, match="signature"):
        StorageService.validate_upload(fake_pdf, allowed_extensions={".pdf"})

    disguised_executable = UploadFile(
        filename="notes.txt", file=io.BytesIO(b"MZ" + b"\x00" * 20)
    )
    with pytest.raises(ValueError, match="signature"):
        StorageService.validate_upload(
            disguised_executable, allowed_extensions={".txt"}
        )


def test_preview_escapes_text_and_markdown(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_PATH", str(tmp_path))
    text_name, _ = StorageService.save_bytes("chat", 7, b'<script>alert(1)</script>', ".txt")
    text_result = preview_file("chat", 7, text_name, "x.txt", 25)
    assert text_result["supported"] is True
    assert "<script>" not in text_result["content"]
    assert "&lt;script&gt;" in text_result["content"]

    md_name, _ = StorageService.save_bytes("submission", 7, b'# Title\n<img src=x onerror=alert(1)>', ".md")
    md_result = preview_file("submission", 7, md_name, "x.md", 40)
    assert md_result["content"].startswith("<h1>Title</h1>")
    assert "<img" not in md_result["content"]
    assert "onerror=" in md_result["content"]  # harmless escaped text, never an HTML attribute


def test_office_preview_cache_hit_and_failure_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(settings, "PREVIEW_OFFICE_ENABLED", True)
    stored, size = StorageService.save_bytes("assignment", 3, b"office", ".docx")
    source = StorageService.get_file_path("assignment", 3, stored)
    cache = FilePreviewService.cache_path("assignment", 3, stored, size, 2)
    cache.parent.mkdir(parents=True)
    cache.write_bytes(b"%PDF cache")
    with patch("backend.app.services.file_preview_service.subprocess.run") as run:
        result = FilePreviewService.preview(path=source, original_name="a.docx", stored_name=stored,
                                            mime_type="application/octet-stream", size=size,
                                            scope="assignment", user_id=3, version=2)
    assert result["supported"] is True and result["preview_url"] == str(cache)
    run.assert_not_called()

    cache.unlink()
    with patch("backend.app.services.file_preview_service.shutil.which", return_value=None):
        result = preview_file("assignment", 3, stored, "a.docx", size, 2)
    assert result == {"supported": False, "preview_url": None, "content": None,
                      "message": "暂不支持预览，请下载查看", "format": None}


def test_preview_cache_cleanup(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_PATH", str(tmp_path))
    old = tmp_path / "preview_cache" / "chat" / "1" / "old.pdf"
    fresh = tmp_path / "preview_cache" / "chat" / "1" / "fresh.pdf"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"old")
    fresh.write_bytes(b"fresh")
    old_time = time.time() - 3 * 86400
    os.utime(old, (old_time, old_time))
    assert cleanup_preview_cache(1) == 1
    assert not old.exists() and fresh.exists()


def test_runtime_config_persists_validated_values(db):
    original = RuntimeConfigService.current()
    try:
        result = RuntimeConfigService.update(db, {"class_name": "测试班", "default_quota_mb": 256,
                                                   "assignment_reminder_hours": [2, 24, 2]}, 1)
        assert result["class_name"] == "测试班"
        assert result["assignment_reminder_hours"] == [24, 2]
        assert db.get(RuntimeConfig, "default_quota_mb").value_json == "256"
        settings.CLASS_NAME = "环境班"
        assert RuntimeConfigService.load(db)["class_name"] == "测试班"
        with pytest.raises(ValueError):
            RuntimeConfigService.update(db, {"ai_api_key": "secret"}, 1)
        with pytest.raises(ValueError):
            RuntimeConfigService.update(db, {"login_max_attempts": True}, 1)
    finally:
        RuntimeConfigService._apply(original)
