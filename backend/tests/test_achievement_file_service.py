import io
from pathlib import Path

import pytest
from fastapi import UploadFile

from backend.app.core.config import settings
from backend.app.services.achievement_files import AchievementFileService


def _upload(name: str, content: bytes, mime: str) -> UploadFile:
    return UploadFile(filename=name, file=io.BytesIO(content), headers={"content-type": mime})


def test_upload_validate_and_remove_achievement_files(tmp_path: Path) -> None:
    previous_storage = settings.STORAGE_PATH
    previous_limit = settings.ACHIEVEMENT_FILE_MAX_MB
    settings.STORAGE_PATH = str(tmp_path)
    settings.ACHIEVEMENT_FILE_MAX_MB = 1
    try:
        proof = AchievementFileService.upload(
            7, _upload("获奖证书.pdf", b"%PDF-1.7 proof", "application/pdf")
        )
        assert proof["name"] == "获奖证书.pdf"
        assert proof["mime"] == "application/pdf"
        assert proof["size"] > 0
        assert AchievementFileService.get_path(7, proof["id"]).endswith(proof["id"])

        normalized = AchievementFileService.normalize_proofs([proof])
        AchievementFileService.validate_owned(7, normalized)
        with pytest.raises(ValueError, match="不存在或无权访问"):
            AchievementFileService.validate_owned(8, normalized)

        AchievementFileService.delete_removed(7, normalized, [])
        with pytest.raises(ValueError, match="不存在"):
            AchievementFileService.get_path(7, proof["id"])
    finally:
        settings.STORAGE_PATH = previous_storage
        settings.ACHIEVEMENT_FILE_MAX_MB = previous_limit


@pytest.mark.parametrize(
    ("name", "mime"),
    [
        ("材料.txt", "text/plain"),
        ("材料.pdf", "text/plain"),
        ("材料.exe", "application/pdf"),
    ],
)
def test_upload_rejects_invalid_file_types(tmp_path: Path, name: str, mime: str) -> None:
    previous_storage = settings.STORAGE_PATH
    settings.STORAGE_PATH = str(tmp_path)
    try:
        with pytest.raises(ValueError, match="仅支持"):
            AchievementFileService.upload(1, _upload(name, b"content", mime))
    finally:
        settings.STORAGE_PATH = previous_storage


def test_upload_rejects_empty_and_oversized_files(tmp_path: Path) -> None:
    previous_storage = settings.STORAGE_PATH
    previous_limit = settings.ACHIEVEMENT_FILE_MAX_MB
    settings.STORAGE_PATH = str(tmp_path)
    settings.ACHIEVEMENT_FILE_MAX_MB = 1
    try:
        with pytest.raises(ValueError, match="不能为空"):
            AchievementFileService.upload(
                1, _upload("empty.png", b"", "image/png")
            )
        with pytest.raises(ValueError, match="不能超过"):
            AchievementFileService.upload(
                1,
                _upload("large.jpg", b"x" * (1024 * 1024 + 1), "image/jpeg"),
            )
        assert not any(tmp_path.rglob("*.*"))
    finally:
        settings.STORAGE_PATH = previous_storage
        settings.ACHIEVEMENT_FILE_MAX_MB = previous_limit
