from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.app.models.achievement import Achievement
from backend.app.core.pagination import normalize_page, normalize_page_size
from backend.app.core.database import local_now


class AchievementRepository:
    @staticmethod
    def get_by_id(db: Session, achievement_id: int) -> Optional[Achievement]:
        return db.query(Achievement).filter(Achievement.id == achievement_id, Achievement.deleted_at.is_(None)).first()

    @staticmethod
    def get_by_id_for_user(db: Session, achievement_id: int, user_id: int) -> Optional[Achievement]:
        return db.query(Achievement).filter(
            Achievement.id == achievement_id,
            Achievement.user_id == user_id,
            Achievement.deleted_at.is_(None),
        ).first()

    @staticmethod
    def create(db: Session, user_id: int, **kwargs) -> Achievement:
        achievement = Achievement(user_id=user_id, **kwargs)
        db.add(achievement)
        db.commit()
        db.refresh(achievement)
        return achievement

    @staticmethod
    def update(db: Session, achievement: Achievement, **kwargs) -> Achievement:
        for key, value in kwargs.items():
            if hasattr(achievement, key):
                setattr(achievement, key, value)
        db.commit()
        db.refresh(achievement)
        return achievement

    @staticmethod
    def update_status(db: Session, achievement: Achievement, status: str) -> Achievement:
        achievement.status = status
        if status == "approved":
            achievement.updated_at = local_now()
        db.commit()
        db.refresh(achievement)
        return achievement

    @staticmethod
    def soft_delete(db: Session, achievement: Achievement) -> Achievement:
        achievement.deleted_at = local_now()
        db.commit()
        db.refresh(achievement)
        return achievement

    @staticmethod
    def list_by_user(
        db: Session, user_id: int, page: int = 1, page_size: int = 20,
        category: Optional[str] = None, status: Optional[str] = None,
        year: Optional[str] = None,
    ) -> tuple[list[Achievement], int]:
        page = normalize_page(page)
        page_size = normalize_page_size(page_size)
        query = db.query(Achievement).filter(Achievement.user_id == user_id, Achievement.deleted_at.is_(None))
        if category:
            query = query.filter(Achievement.category == category)
        if status:
            query = query.filter(Achievement.status == status)
        if year:
            query = query.filter(Achievement.achievement_date.like(f"{year}-%"))
        total = query.count()
        items = query.order_by(
            Achievement.achievement_date.desc(), Achievement.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size).all()
        return items, total

    @staticmethod
    def list_years_by_user(db: Session, user_id: int) -> list[dict[str, int]]:
        year_expression = func.substr(Achievement.achievement_date, 1, 4)
        rows = db.query(
            year_expression.label("year"),
            func.count(Achievement.id).label("count"),
        ).filter(
            Achievement.user_id == user_id,
            Achievement.deleted_at.is_(None),
            Achievement.achievement_date.is_not(None),
        ).group_by(year_expression).all()

        years = [
            {"year": int(year), "count": int(count)}
            for year, count in rows
            if year and len(str(year)) == 4 and str(year).isascii() and str(year).isdigit()
        ]
        return sorted(years, key=lambda item: item["year"], reverse=True)

    @staticmethod
    def list_public(
        db: Session, page: int = 1, page_size: int = 20,
        category: Optional[str] = None, q: Optional[str] = None,
    ) -> tuple[list[Achievement], int]:
        page = normalize_page(page)
        page_size = normalize_page_size(page_size)
        query = db.query(Achievement).filter(
            Achievement.is_public.is_(True), Achievement.status == "approved", Achievement.deleted_at.is_(None)
        )
        if category:
            query = query.filter(Achievement.category == category)
        if q:
            search = f"%{q}%"
            query = query.filter(or_(Achievement.title.ilike(search), Achievement.description.ilike(search)))
        total = query.count()
        items = query.order_by(
            Achievement.achievement_date.desc(), Achievement.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size).all()
        return items, total

    @staticmethod
    def list_all(
        db: Session, page: int = 1, page_size: int = 20,
        status: Optional[str] = None, q: Optional[str] = None,
        category: Optional[str] = None, year: Optional[str] = None,
    ) -> tuple[list[Achievement], int]:
        page = normalize_page(page)
        page_size = normalize_page_size(page_size)
        query = db.query(Achievement).filter(Achievement.deleted_at.is_(None))
        if status:
            query = query.filter(Achievement.status == status)
        if category:
            query = query.filter(Achievement.category == category)
        if year:
            query = query.filter(Achievement.achievement_date.like(f"{year}-%"))
        if q:
            search = f"%{q}%"
            query = query.filter(or_(Achievement.title.ilike(search), Achievement.description.ilike(search)))
        total = query.count()
        items = query.order_by(
            Achievement.achievement_date.desc(), Achievement.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size).all()
        return items, total
