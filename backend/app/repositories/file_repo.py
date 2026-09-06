from datetime import datetime, timezone
import re
from typing import Optional

from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from backend.app.models.file import KnowledgeFile, FileChunk, KnowledgeFolder, KnowledgeFileVersion
from backend.app.core.pagination import normalize_page, normalize_page_size
from backend.app.core.database import local_now


def _extract_keywords(query: str) -> list[str]:
    """
    从查询中提取关键词，支持中文（无空格分词）。
    策略：用 \\W+ 切分（中英文标点、空白皆为非词字符，CJK 属于 \\w）；
    英文 token 保留原词；CJK 短词保留原词，长词额外生成 bigram 提升召回。
    """
    # \W 在 Python3 re 默认 Unicode 下 = 非 [字母/数字/下划线]，含中英文标点与空白
    tokens = [t for t in re.split(r"\W+", query) if t]

    keywords: set[str] = set()
    for token in tokens:
        if re.fullmatch(r"[\x00-\x7f]+", token):
            # 英文/数字 token
            if len(token) >= 2:
                keywords.add(token)
        else:
            # CJK token
            if len(token) <= 4:
                keywords.add(token)
            if len(token) >= 2:
                # 生成 bigram 提升中文召回
                for i in range(len(token) - 1):
                    keywords.add(token[i : i + 2])

    return list(keywords)


class FileRepository:
    @staticmethod
    def list_folders(db: Session, scope: str, owner_user_id: int) -> list[KnowledgeFolder]:
        return (
            db.query(KnowledgeFolder)
            .filter(
                KnowledgeFolder.scope == scope,
                KnowledgeFolder.owner_user_id == owner_user_id,
                KnowledgeFolder.deleted_at.is_(None),
            )
            .order_by(KnowledgeFolder.name)
            .all()
        )

    @staticmethod
    def get_folder(db: Session, folder_id: int) -> Optional[KnowledgeFolder]:
        return (
            db.query(KnowledgeFolder)
            .filter(KnowledgeFolder.id == folder_id, KnowledgeFolder.deleted_at.is_(None))
            .first()
        )

    @staticmethod
    def create_folder(db: Session, scope: str, owner_user_id: int, created_by: int, name: str) -> KnowledgeFolder:
        if not name or len(name.strip()) > 100:
            raise ValueError("文件夹名称不能为空且不超过100个字符")
        if (
            db.query(KnowledgeFolder)
            .filter(
                KnowledgeFolder.scope == scope,
                KnowledgeFolder.owner_user_id == owner_user_id,
                KnowledgeFolder.name == name.strip(),
                KnowledgeFolder.deleted_at.is_(None),
            )
            .first()
        ):
            raise ValueError("同名文件夹已存在")
        folder = KnowledgeFolder(scope=scope, owner_user_id=owner_user_id, created_by=created_by, name=name.strip())
        db.add(folder)
        db.commit()
        db.refresh(folder)
        return folder

    @staticmethod
    def rename_folder(db: Session, folder: KnowledgeFolder, name: str) -> KnowledgeFolder:
        name = name.strip()
        if not name or len(name) > 100:
            raise ValueError("文件夹名称不能为空且不超过100个字符")
        duplicate = (
            db.query(KnowledgeFolder)
            .filter(
                KnowledgeFolder.scope == folder.scope,
                KnowledgeFolder.owner_user_id == folder.owner_user_id,
                KnowledgeFolder.name == name,
                KnowledgeFolder.id != folder.id,
                KnowledgeFolder.deleted_at.is_(None),
            )
            .first()
        )
        if duplicate:
            raise ValueError("同名文件夹已存在")
        folder.name = name
        db.commit()
        db.refresh(folder)
        return folder

    @staticmethod
    def delete_folder(db: Session, folder: KnowledgeFolder) -> None:
        if (
            db.query(KnowledgeFile)
            .filter(KnowledgeFile.folder_id == folder.id, KnowledgeFile.deleted_at.is_(None))
            .count()
        ):
            raise ValueError("请先移动或删除文件夹内文件")
        folder.deleted_at = local_now()
        db.commit()

    @staticmethod
    def move_file(db: Session, file: KnowledgeFile, folder: KnowledgeFolder | None) -> KnowledgeFile:
        if folder and (folder.scope != file.scope or folder.owner_user_id != file.owner_user_id):
            raise ValueError("目标文件夹无效")
        file.folder_id = folder.id if folder else None
        db.commit()
        db.refresh(file)
        return file

    @staticmethod
    def list_versions(db: Session, file_id: int) -> list[KnowledgeFileVersion]:
        return (
            db.query(KnowledgeFileVersion)
            .filter(KnowledgeFileVersion.file_id == file_id)
            .order_by(KnowledgeFileVersion.version.desc())
            .all()
        )

    @staticmethod
    def create(
        db: Session,
        owner_user_id: int,
        scope: str,
        original_name: str,
        stored_name: str,
        mime_type: str,
        size: int,
        tag: Optional[str] = None,
        folder_id: int | None = None,
        class_id: int | None = None,
    ) -> KnowledgeFile:
        f = KnowledgeFile(
            owner_user_id=owner_user_id,
            scope=scope,
            original_name=original_name,
            stored_name=stored_name,
            mime_type=mime_type,
            size=size,
            tag=tag,
            folder_id=folder_id,
            class_id=class_id if scope == "class" else None,
        )
        db.add(f)
        db.commit()
        db.refresh(f)
        return f

    @staticmethod
    def get_by_id(db: Session, file_id: int, include_deleted: bool = False) -> Optional[KnowledgeFile]:
        query = db.query(KnowledgeFile).filter(KnowledgeFile.id == file_id)
        if not include_deleted:
            query = query.filter(KnowledgeFile.deleted_at.is_(None))
        return query.first()

    @staticmethod
    def list_personal(
        db: Session,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
        q: Optional[str] = None,
    ) -> tuple[list[KnowledgeFile], int]:
        page = normalize_page(page)
        page_size = normalize_page_size(page_size)
        query = db.query(KnowledgeFile).filter(
            KnowledgeFile.scope == "personal",
            KnowledgeFile.owner_user_id == user_id,
            KnowledgeFile.deleted_at.is_(None),
        )
        if q:
            query = query.filter(KnowledgeFile.original_name.ilike(f"%{q}%"))
        total = query.count()
        items = query.order_by(desc(KnowledgeFile.created_at)).offset((page - 1) * page_size).limit(page_size).all()
        return items, total

    @staticmethod
    def list_class(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        q: Optional[str] = None,
    ) -> tuple[list[KnowledgeFile], int]:
        page = normalize_page(page)
        page_size = normalize_page_size(page_size)
        query = db.query(KnowledgeFile).filter(
            KnowledgeFile.scope == "class",
            KnowledgeFile.deleted_at.is_(None),
        )
        if q:
            query = query.filter(KnowledgeFile.original_name.ilike(f"%{q}%"))
        total = query.count()
        items = (
            query.order_by(desc(KnowledgeFile.is_pinned), desc(KnowledgeFile.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    @staticmethod
    def update(db: Session, file: KnowledgeFile, **kwargs) -> KnowledgeFile:
        for key, value in kwargs.items():
            if hasattr(file, key) and value is not None:
                setattr(file, key, value)
        db.commit()
        db.refresh(file)
        return file

    @staticmethod
    def soft_delete(db: Session, file: KnowledgeFile) -> KnowledgeFile:
        file.deleted_at = local_now()
        db.commit()
        db.refresh(file)
        return file

    @staticmethod
    def increment_download(db: Session, file: KnowledgeFile) -> None:
        file.download_count += 1
        db.commit()

    @staticmethod
    def update_parse_status(
        db: Session,
        file: KnowledgeFile,
        status: str,
        error: Optional[str] = None,
    ) -> None:
        file.parse_status = status
        file.parse_error = error
        db.commit()

    @staticmethod
    def add_chunks(db: Session, file_id: int, chunks: list[dict]) -> None:
        """批量添加文本切片"""
        for i, chunk in enumerate(chunks):
            c = FileChunk(
                file_id=file_id,
                chunk_index=i,
                page_no=chunk.get("page_no"),
                content=chunk["content"],
                token_count=chunk.get("token_count"),
            )
            db.add(c)
        db.commit()

    @staticmethod
    def delete_chunks(db: Session, file_id: int) -> None:
        db.query(FileChunk).filter(FileChunk.file_id == file_id).delete()
        db.commit()

    @staticmethod
    def search_chunks(
        db: Session,
        query: str,
        scope: str = "personal",
        user_id: Optional[int] = None,
        class_id: int | None = None,
        limit: int = 5,
    ) -> list[dict]:
        """
        关键词检索文本切片
        先权限过滤，再检索（严禁先检索后过滤）
        中文无空格分词，使用 bigram + 关键词 OR 匹配，按命中数评分
        返回: [{"file_id", "file_name", "chunk_content", "page_no", "score"}]
        """
        base_query = (
            db.query(FileChunk, KnowledgeFile)
            .join(KnowledgeFile, FileChunk.file_id == KnowledgeFile.id)
            .filter(KnowledgeFile.deleted_at.is_(None), KnowledgeFile.parse_status == "ready")
        )

        # 权限过滤（必须在前）
        if scope == "personal":
            base_query = base_query.filter(
                KnowledgeFile.scope == "personal",
                KnowledgeFile.owner_user_id == user_id,
            )
        elif scope == "class":
            base_query = base_query.filter(KnowledgeFile.scope == "class")
            if class_id is not None:
                base_query = base_query.filter(
                    or_(KnowledgeFile.class_id == class_id, KnowledgeFile.class_id.is_(None))
                )
        else:  # all
            base_query = base_query.filter(
                or_(
                    KnowledgeFile.scope == "class",
                    KnowledgeFile.owner_user_id == user_id,
                )
            )

        # 关键词提取（支持中文 bigram）
        keywords = _extract_keywords(query)
        if not keywords:
            return []

        # OR 匹配：任一关键词命中即为候选，再按命中数评分排序
        keyword_filters = [FileChunk.content.ilike(f"%{kw}%") for kw in keywords]
        candidates = base_query.filter(or_(*keyword_filters)).limit(limit * 5).all()

        scored = []
        for chunk, file in candidates:
            content_lower = chunk.content.lower()
            matched = sum(1 for kw in keywords if kw.lower() in content_lower)
            scored.append(
                {
                    "file_id": file.id,
                    "file_name": file.original_name,
                    "chunk_content": chunk.content[:500],
                    "page_no": chunk.page_no,
                    "score": matched,
                }
            )
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    @staticmethod
    def list_expired_deleted(db: Session, before_dt: datetime, limit: int = 100) -> list[KnowledgeFile]:
        """列出软删除时间早于 before_dt 的文件（超期待物理清理）"""
        return (
            db.query(KnowledgeFile)
            .filter(KnowledgeFile.deleted_at.isnot(None), KnowledgeFile.deleted_at < before_dt)
            .limit(limit)
            .all()
        )

    @staticmethod
    def hard_delete(db: Session, file: KnowledgeFile) -> None:
        """硬删除数据库记录（物理清理时调用）"""
        db.query(FileChunk).filter(FileChunk.file_id == file.id).delete()
        db.query(KnowledgeFile).filter(KnowledgeFile.id == file.id).delete()
        db.commit()

    @staticmethod
    def get_user_file_count(db: Session, user_id: int) -> int:
        return (
            db.query(KnowledgeFile)
            .filter(
                KnowledgeFile.scope == "personal",
                KnowledgeFile.owner_user_id == user_id,
                KnowledgeFile.deleted_at.is_(None),
            )
            .count()
        )

    @staticmethod
    def get_user_total_size(db: Session, user_id: int) -> int:
        from sqlalchemy import func

        result = (
            db.query(func.sum(KnowledgeFile.size))
            .filter(
                KnowledgeFile.scope == "personal",
                KnowledgeFile.owner_user_id == user_id,
                KnowledgeFile.deleted_at.is_(None),
            )
            .scalar()
        )
        return result or 0
