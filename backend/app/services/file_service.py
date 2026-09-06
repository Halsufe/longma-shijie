import logging
import os

from sqlalchemy.orm import Session

from backend.app.core.storage import StorageService
from backend.app.core.config import settings
from backend.app.repositories.file_repo import FileRepository
from backend.app.ai.parser import ALLOWED_EXTENSIONS, parse_file, is_allowed_extension

logger = logging.getLogger(__name__)


class FileService:
    @staticmethod
    def upload_and_parse(
        db: Session,
        user_id: int,
        scope: str,
        file,
        tag: str | None = None,
        folder_id: int | None = None,
        class_id: int | None = None,
    ) -> dict:
        """
        上传文件并自动解析
        返回: file_info dict
        """
        from fastapi import UploadFile

        # 校验文件名
        if not file.filename:
            raise ValueError("文件名为空")
        if not is_allowed_extension(file.filename):
            raise ValueError(f"不支持的文件类型: {file.filename}")

        file_size = StorageService.validate_upload(
            file,
            max_bytes=settings.DEFAULT_QUOTA_MB * 1024 * 1024,
            allowed_extensions=ALLOWED_EXTENSIONS,
        )

        # 配额校验（仅个人知识库）
        if scope == "personal":
            used = FileRepository.get_user_total_size(db, user_id)
            quota = settings.DEFAULT_QUOTA_MB * 1024 * 1024
            if used + file_size > quota:
                raise ValueError(f"配额不足: 已用 {used // 1024 // 1024}MB, 配额 {settings.DEFAULT_QUOTA_MB}MB")

        # 保存文件
        stored_name, mime_type, size = StorageService.save_file(scope, user_id, file)

        # 创建数据库记录
        kf = FileRepository.create(
            db,
            owner_user_id=user_id,
            scope=scope,
            original_name=file.filename,
            stored_name=stored_name,
            mime_type=mime_type,
            size=size,
            tag=tag,
            folder_id=folder_id,
            class_id=class_id,
        )

        # 同步解析（开发阶段，数据量小）
        FileService.parse_file_sync(db, kf, scope, user_id)

        return {
            "id": kf.id,
            "original_name": kf.original_name,
            "size": kf.size,
            "parse_status": kf.parse_status,
            "parse_error": kf.parse_error,
        }

    @staticmethod
    def parse_file_sync(db: Session, kf, scope: str, user_id: int) -> None:
        """同步解析文件"""
        FileRepository.update_parse_status(db, kf, "processing")

        try:
            file_path = StorageService.get_file_path(scope, user_id, kf.stored_name)
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"文件不存在: {kf.stored_name}")

            chunks = parse_file(file_path, kf.original_name)
            if chunks:
                FileRepository.add_chunks(db, kf.id, chunks)
                FileRepository.update_parse_status(db, kf, "ready")
                logger.info("File parsed: %s, %d chunks", kf.original_name, len(chunks))
            else:
                FileRepository.update_parse_status(db, kf, "failed", "未提取到文本内容")
        except Exception as e:
            logger.exception("Parse failed: %s", kf.original_name)
            FileRepository.update_parse_status(db, kf, "failed", str(e))

    @staticmethod
    def delete_file(db: Session, file_id: int, user_id: int, scope: str) -> dict:
        """删除文件（软删除 + 清理 chunks）"""
        kf = FileRepository.get_by_id(db, file_id)
        if not kf or kf.scope != scope:
            raise ValueError("文件不存在")

        if scope == "personal" and kf.owner_user_id != user_id:
            raise ValueError("无权删除他人文件")

        # 软删除数据库记录
        FileRepository.soft_delete(db, kf)
        # 删除 chunks
        FileRepository.delete_chunks(db, file_id)
        # 物理文件保留（7天恢复期），后台任务清理

        return {"id": file_id, "message": "文件已删除"}

    @staticmethod
    def get_file_path_for_download(db: Session, file_id: int, user_id: int) -> tuple[str, str]:
        """获取下载路径，返回 (file_path, original_name)"""
        kf = FileRepository.get_by_id(db, file_id)
        if not kf:
            raise ValueError("文件不存在")

        # 权限检查
        if kf.scope == "personal" and kf.owner_user_id != user_id:
            raise ValueError("无权下载")

        file_path = StorageService.get_file_path(kf.scope, kf.owner_user_id, kf.stored_name)
        if not os.path.exists(file_path):
            raise ValueError("文件不存在于磁盘")

        FileRepository.increment_download(db, kf)
        return file_path, kf.original_name
