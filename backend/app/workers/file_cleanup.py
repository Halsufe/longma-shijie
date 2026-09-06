"""文件清理 worker：物理删除软删除超过保留期的文件"""
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.storage import StorageService
from backend.app.repositories.file_repo import FileRepository
from backend.app.core.database import local_now

logger = logging.getLogger(__name__)


def run_cleanup(db: Session, retention_days: int | None = None) -> int:
    """
    清理软删除超过 retention_days 的文件：删物理文件 + 硬删 DB 记录。
    返回清理数量。
    """
    days = retention_days if retention_days is not None else settings.FILE_RETENTION_DAYS
    cutoff = local_now() - timedelta(days=days)
    expired = FileRepository.list_expired_deleted(db, before_dt=cutoff, limit=200)

    cleaned = 0
    for kf in expired:
        try:
            StorageService.delete_file(kf.scope, kf.owner_user_id, kf.stored_name)
            FileRepository.hard_delete(db, kf)
            cleaned += 1
            logger.info("Cleanup: hard-deleted file id=%s name=%s", kf.id, kf.stored_name)
        except Exception as e:
            logger.warning("Cleanup failed for file id=%s: %s", kf.id, e)
    if cleaned:
        logger.info("Cleanup: removed %d expired files (retention=%d days)", cleaned, days)
    return cleaned


def cleanup_preview_cache(ttl_days: int | None = None) -> int:
    days = ttl_days if ttl_days is not None else settings.PREVIEW_CACHE_TTL_DAYS
    cutoff = local_now().timestamp() - timedelta(days=days).total_seconds()
    root = os.path.join(settings.STORAGE_PATH, "preview_cache")
    cleaned = 0
    if not os.path.isdir(root):
        return cleaned
    for dirpath, _, filenames in os.walk(root):
        for filename in filenames:
            path = os.path.join(dirpath, filename)
            try:
                if os.path.getmtime(path) < cutoff:
                    os.remove(path)
                    cleaned += 1
            except OSError as exc:
                logger.warning("Preview cache cleanup failed for %s: %s", path, exc)
    return cleaned


async def _cleanup_loop():
    """每小时跑一次清理"""
    from backend.app.core.database import SessionLocal

    while True:
        await asyncio.sleep(3600)
        try:
            db = SessionLocal()
            try:
                run_cleanup(db)
                cleanup_preview_cache()
            finally:
                db.close()
        except Exception as e:
            logger.warning("Cleanup loop error: %s", e)


def start_cleanup_loop(app):
    """应用启动时挂载后台清理任务"""
    from backend.app.core.config import settings as _s

    if _s.ENV == "test":
        return
    asyncio.create_task(_cleanup_loop())
