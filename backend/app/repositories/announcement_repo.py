from __future__ import annotations

from datetime import date, datetime, timedelta
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from backend.app.announcements.adapters.base import AnnouncementDocument, AttachmentLink, normalize_url
from backend.app.core.database import local_now
from backend.app.models.announcement import (
    AnnouncementAttachment, AnnouncementDigest, AnnouncementOrigin, AnnouncementSource,
    AnnouncementStatus, SchoolAnnouncement,
)


class AnnouncementRepository:
    @staticmethod
    def get_source(db: Session, code: str) -> AnnouncementSource | None:
        return db.query(AnnouncementSource).filter(AnnouncementSource.code == code).first()

    @staticmethod
    def list_sources(db: Session, enabled_only: bool = False) -> list[AnnouncementSource]:
        query = db.query(AnnouncementSource)
        if enabled_only:
            query = query.filter(AnnouncementSource.enabled.is_(True))
        return query.order_by(AnnouncementSource.display_order, AnnouncementSource.id).all()

    @staticmethod
    def upsert_source(db: Session, *, code: str, name: str, list_url: str, adapter_key: str, display_order: int = 0) -> AnnouncementSource:
        source = AnnouncementRepository.get_source(db, code)
        if source is None:
            source = AnnouncementSource(code=code, name=name, list_url=list_url, adapter_key=adapter_key, display_order=display_order)
            db.add(source)
        else:
            source.name, source.list_url, source.adapter_key, source.display_order = name, list_url, adapter_key, display_order
        db.flush()
        return source

    @staticmethod
    def get_by_id(db: Session, announcement_id: int) -> SchoolAnnouncement | None:
        return db.query(SchoolAnnouncement).filter(SchoolAnnouncement.id == announcement_id).first()

    @staticmethod
    def get_by_origin(db: Session, source_id: int, canonical_url: str) -> SchoolAnnouncement | None:
        origin = db.query(AnnouncementOrigin).filter(AnnouncementOrigin.source_id == source_id, AnnouncementOrigin.canonical_url == canonical_url).first()
        return AnnouncementRepository.get_by_id(db, origin.announcement_id) if origin else None

    @staticmethod
    def create_from_document(db: Session, source: AnnouncementSource, document: AnnouncementDocument, *, relevance_status: str = "uncertain") -> SchoolAnnouncement:
        url = normalize_url(document.url)
        existing = AnnouncementRepository.get_by_origin(db, source.id, url)
        published = document.published_at.date() if isinstance(document.published_at, datetime) else document.published_at
        if published is None:
            published = local_now().date()
        if existing:
            existing.body_text = document.body
            existing.title = document.title or existing.title
            existing.published_at = published
            existing.status = AnnouncementStatus.READY.value if document.body else AnnouncementStatus.PARTIAL.value
            db.query(AnnouncementOrigin).filter(AnnouncementOrigin.announcement_id == existing.id, AnnouncementOrigin.source_id == source.id, AnnouncementOrigin.canonical_url == url).update({"last_seen_at": local_now()})
            announcement = existing
        else:
            announcement = SchoolAnnouncement(
                title=document.title, published_at=published, body_text=document.body,
                relevance_status=relevance_status, status=AnnouncementStatus.READY.value if document.body else AnnouncementStatus.PARTIAL.value,
                retention_until=SchoolAnnouncement.retention_date(published),
            )
            db.add(announcement)
            db.flush()
            db.add(AnnouncementOrigin(announcement_id=announcement.id, source_id=source.id, canonical_url=url, source_title=document.title))
        for attachment in document.attachments:
            normalized = normalize_url(attachment.url, document.url)
            exists = db.query(AnnouncementAttachment).filter(AnnouncementAttachment.announcement_id == announcement.id, AnnouncementAttachment.url == normalized).first()
            if not exists:
                db.add(AnnouncementAttachment(announcement_id=announcement.id, name=attachment.name, url=normalized, media_type=attachment.media_type))
        db.flush()
        return announcement

    @staticmethod
    def list_visible(db: Session, *, page: int = 1, page_size: int = 20, keyword: str | None = None, source_id: int | None = None, published_from: date | None = None, published_to: date | None = None) -> tuple[list[SchoolAnnouncement], int]:
        today = local_now().date()
        query = db.query(SchoolAnnouncement).join(AnnouncementOrigin, AnnouncementOrigin.announcement_id == SchoolAnnouncement.id).filter(
            SchoolAnnouncement.relevance_status.in_(["relevant", "uncertain"]), SchoolAnnouncement.status.in_(["ready", "partial"]),
            or_(SchoolAnnouncement.retention_until.is_(None), SchoolAnnouncement.retention_until >= today),
        )
        if keyword:
            term = f"%{keyword.strip()}%"
            query = query.filter(or_(SchoolAnnouncement.title.ilike(term), SchoolAnnouncement.body_text.ilike(term), SchoolAnnouncement.summary_text.ilike(term)))
        if source_id:
            query = query.filter(AnnouncementOrigin.source_id == source_id)
        if published_from:
            query = query.filter(SchoolAnnouncement.published_at >= published_from)
        if published_to:
            query = query.filter(SchoolAnnouncement.published_at <= published_to)
        query = query.distinct()
        total = query.count()
        items = query.order_by(SchoolAnnouncement.published_at.desc(), SchoolAnnouncement.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return items, total

    @staticmethod
    def find_expired(db: Session, today: date | None = None, limit: int = 100) -> list[SchoolAnnouncement]:
        return db.query(SchoolAnnouncement).filter(SchoolAnnouncement.retention_until < (today or local_now().date()), SchoolAnnouncement.status != AnnouncementStatus.EXPIRED.value).limit(limit).all()

    @staticmethod
    def mark_expired_and_cleanup(db: Session, announcement: SchoolAnnouncement) -> None:
        announcement.status = AnnouncementStatus.EXPIRED.value
        announcement.body_text = ""
        announcement.summary_text = None
        announcement.key_fields_json = "{}"
        db.query(AnnouncementAttachment).filter(AnnouncementAttachment.announcement_id == announcement.id).delete(synchronize_session=False)
        db.query(AnnouncementOrigin).filter(AnnouncementOrigin.announcement_id == announcement.id).delete(synchronize_session=False)


class AnnouncementSourceRepository:
    """Compatibility facade used by application startup and worker seed jobs."""

    @staticmethod
    def seed_defaults(db: Session) -> int:
        defaults = (
            ("cufe_main", "中央财经大学主站", "https://www.cufe.edu.cn/", "cufe_main"),
            ("cufe_youth", "中央财经大学团委", "https://youth.cufe.edu.cn/", "cufe_youth"),
            ("cufe_mse", "管理科学与工程学院", "https://mse.cufe.edu.cn/", "cufe_mse"),
            ("cufe_jwc", "教务处", "https://jwc.cufe.edu.cn/", "cufe_jwc"),
        )
        added = 0
        for order, (code, name, url, adapter_key) in enumerate(defaults):
            if AnnouncementRepository.get_source(db, code) is None:
                AnnouncementRepository.upsert_source(db, code=code, name=name, list_url=url, adapter_key=adapter_key, display_order=order)
                added += 1
        db.commit()
        return added
