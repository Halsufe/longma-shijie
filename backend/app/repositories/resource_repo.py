from typing import Optional, List
from datetime import datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.models.resource import Resource, ResourceFavorite, ResourceLike
from backend.app.core.pagination import normalize_page, normalize_page_size
from backend.app.core.database import local_now


class ResourceRepository:
    @staticmethod
    def get_by_id(db: Session, resource_id: int) -> Optional[Resource]:
        return db.query(Resource).filter(Resource.id == resource_id, Resource.deleted_at.is_(None)).first()

    @staticmethod
    def create(db: Session, author_id: int, **kwargs) -> Resource:
        resource = Resource(author_id=author_id, **kwargs)
        db.add(resource)
        db.commit()
        db.refresh(resource)
        ResourceRepository._refresh_embedding(db, resource)
        return resource

    @staticmethod
    def update(db: Session, resource: Resource, **kwargs) -> Resource:
        for key, value in kwargs.items():
            if hasattr(resource, key) and value is not None:
                setattr(resource, key, value)
        db.commit()
        db.refresh(resource)
        ResourceRepository._refresh_embedding(db, resource)
        return resource

    @staticmethod
    def update_status(db: Session, resource_id: int, status: str) -> Optional[Resource]:
        resource = db.query(Resource).filter(Resource.id == resource_id).first()
        if not resource:
            return None
        resource.status = status
        db.commit()
        db.refresh(resource)
        ResourceRepository._refresh_embedding(db, resource)
        return resource

    @staticmethod
    def soft_delete(db: Session, resource: Resource) -> Resource:
        resource.deleted_at = local_now()
        db.commit()
        db.refresh(resource)
        ResourceRepository._refresh_embedding(db, resource)
        return resource

    @staticmethod
    def _refresh_embedding(db: Session, resource: Resource) -> None:
        from backend.app.services.semantic_service import SemanticService

        SemanticService.refresh_resource(db, resource)

    @staticmethod
    def increment_view(db: Session, resource: Resource) -> None:
        resource.view_count += 1
        db.commit()

    @staticmethod
    def list_approved(
        db: Session, page: int = 1, page_size: int = 20,
        type: Optional[str] = None, q: Optional[str] = None, tag: Optional[str] = None,
    ) -> tuple[List[Resource], int]:
        page = normalize_page(page)
        page_size = normalize_page_size(page_size)
        query = db.query(Resource).filter(Resource.status == "approved", Resource.deleted_at.is_(None))
        if type:
            query = query.filter(Resource.type == type)
        if q:
            search = f"%{q}%"
            query = query.filter(or_(Resource.title.ilike(search), Resource.content.ilike(search)))
        if tag:
            query = query.filter(Resource.tags_json.contains(tag))
        total = query.count()
        items = query.order_by(Resource.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return items, total

    @staticmethod
    def list_by_author(
        db: Session, author_id: int, page: int = 1, page_size: int = 20,
    ) -> tuple[List[Resource], int]:
        page = normalize_page(page)
        page_size = normalize_page_size(page_size)
        query = db.query(Resource).filter(Resource.author_id == author_id, Resource.deleted_at.is_(None))
        total = query.count()
        items = query.order_by(Resource.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return items, total

    @staticmethod
    def list_by_status(
        db: Session, status: str, page: int = 1, page_size: int = 20,
    ) -> tuple[List[Resource], int]:
        page = normalize_page(page)
        page_size = normalize_page_size(page_size)
        query = db.query(Resource).filter(Resource.status == status, Resource.deleted_at.is_(None))
        total = query.count()
        items = query.order_by(Resource.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return items, total

    @staticmethod
    def favorite(db: Session, user_id: int, resource_id: int) -> None:
        existing = db.query(ResourceFavorite).filter(
            ResourceFavorite.user_id == user_id, ResourceFavorite.resource_id == resource_id
        ).first()
        if not existing:
            fav = ResourceFavorite(user_id=user_id, resource_id=resource_id)
            db.add(fav)
            db.commit()

    @staticmethod
    def unfavorite(db: Session, user_id: int, resource_id: int) -> None:
        db.query(ResourceFavorite).filter(
            ResourceFavorite.user_id == user_id, ResourceFavorite.resource_id == resource_id
        ).delete()
        db.commit()

    @staticmethod
    def list_favorites(
        db: Session, user_id: int, page: int = 1, page_size: int = 20,
    ) -> tuple[List[Resource], int]:
        page = normalize_page(page)
        page_size = normalize_page_size(page_size)
        fav_ids = [f.resource_id for f in db.query(ResourceFavorite).filter(ResourceFavorite.user_id == user_id).all()]
        if not fav_ids:
            return [], 0
        query = db.query(Resource).filter(Resource.id.in_(fav_ids), Resource.deleted_at.is_(None))
        total = query.count()
        items = query.order_by(Resource.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return items, total

    @staticmethod
    def like(db: Session, user_id: int, resource_id: int) -> None:
        existing = db.query(ResourceLike).filter(
            ResourceLike.user_id == user_id, ResourceLike.resource_id == resource_id
        ).first()
        if not existing:
            like = ResourceLike(user_id=user_id, resource_id=resource_id)
            db.add(like)
            resource = db.query(Resource).filter(Resource.id == resource_id).first()
            if resource:
                resource.like_count += 1
            db.commit()

    @staticmethod
    def unlike(db: Session, user_id: int, resource_id: int) -> None:
        existing = db.query(ResourceLike).filter(
            ResourceLike.user_id == user_id, ResourceLike.resource_id == resource_id
        ).first()
        if existing:
            db.delete(existing)
            resource = db.query(Resource).filter(Resource.id == resource_id).first()
            if resource and resource.like_count > 0:
                resource.like_count -= 1
            db.commit()
