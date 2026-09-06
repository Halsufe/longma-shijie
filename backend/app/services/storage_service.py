import logging
import os

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.models.file import KnowledgeFile
from backend.app.models.user import User
from backend.app.core.storage import StorageService
from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class StorageStatService:
    """存储用量统计"""

    @staticmethod
    def get_usage(db: Session) -> dict:
        """总览：个人/班级存储用量 + 按用户明细"""
        # 个人知识库按用户聚合
        personal_rows = (
            db.query(
                KnowledgeFile.owner_user_id,
                func.sum(KnowledgeFile.size).label("total"),
                func.count(KnowledgeFile.id).label("cnt"),
            )
            .filter(
                KnowledgeFile.scope == "personal",
                KnowledgeFile.deleted_at.is_(None),
            )
            .group_by(KnowledgeFile.owner_user_id)
            .all()
        )

        # 班级总量
        class_total = (
            db.query(func.sum(KnowledgeFile.size))
            .filter(KnowledgeFile.scope == "class", KnowledgeFile.deleted_at.is_(None))
            .scalar()
        ) or 0

        # 用户名映射
        owner_ids = [r.owner_user_id for r in personal_rows]
        users = db.query(User).filter(User.id.in_(owner_ids)).all() if owner_ids else []
        user_map = {u.id: u.name for u in users}

        by_user = []
        personal_total = 0
        for r in personal_rows:
            by_user.append({
                "user_id": r.owner_user_id,
                "name": user_map.get(r.owner_user_id, "未知"),
                "bytes": int(r.total or 0),
                "count": int(r.cnt or 0),
            })
            personal_total += int(r.total or 0)

        by_user.sort(key=lambda x: x["bytes"], reverse=True)

        return {
            "personal_total_bytes": personal_total,
            "class_total_bytes": int(class_total),
            "by_user": by_user,
        }
