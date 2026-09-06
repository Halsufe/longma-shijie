import json
from datetime import datetime
from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.app.models.audit import AuditLog
from backend.app.core.pagination import normalize_page, normalize_page_size


class AuditRepository:
    @staticmethod
    def create(
        db: Session,
        operator_id: Optional[int] = None,
        operator_name: Optional[str] = None,
        action: str = "",
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        result: str = "success",
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        detail: Optional[dict] = None,
    ) -> AuditLog:
        log = AuditLog(
            operator_id=operator_id,
            operator_name=operator_name,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            result=result,
            ip=ip,
            user_agent=user_agent,
            detail=json.dumps(detail, ensure_ascii=False) if detail else None,
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    @staticmethod
    def list(
        db: Session,
        operator_id: Optional[int] = None,
        action: Optional[str] = None,
        target_type: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AuditLog], int]:
        page = normalize_page(page)
        page_size = normalize_page_size(page_size)
        query = db.query(AuditLog)
        if operator_id:
            query = query.filter(AuditLog.operator_id == operator_id)
        if action:
            query = query.filter(AuditLog.action == action)
        if target_type:
            query = query.filter(AuditLog.target_type == target_type)
        if start:
            query = query.filter(AuditLog.created_at >= start)
        if end:
            query = query.filter(AuditLog.created_at <= end)
        total = query.count()
        items = (
            query.order_by(desc(AuditLog.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total
