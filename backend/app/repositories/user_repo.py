from typing import Optional, List
from datetime import datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.models.user import User, UserRole, UserStatus
from backend.app.core.pagination import normalize_page, normalize_page_size
from backend.app.core.database import local_now


class UserRepository:
    @staticmethod
    def get_by_id(db: Session, user_id: int) -> Optional[User]:
        return db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()

    @staticmethod
    def get_by_student_no(db: Session, student_no: str) -> Optional[User]:
        student_no = student_no.strip()
        return db.query(User).filter(User.student_no == student_no, User.deleted_at.is_(None)).first()

    @staticmethod
    def create(
        db: Session,
        student_no: str,
        name: str,
        password_hash: str,
        role: str = UserRole.STUDENT.value,
        status: str = UserStatus.PENDING_CHANGE.value,
    ) -> User:
        user = User(
            student_no=student_no.strip(),
            name=name.strip(),
            password_hash=password_hash,
            role=role,
            status=status,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def update(db: Session, user: User, **kwargs) -> User:
        for key, value in kwargs.items():
            if hasattr(user, key) and value is not None:
                setattr(user, key, value)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def soft_delete(db: Session, user: User) -> User:
        user.deleted_at = local_now()
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def restore(db: Session, user: User) -> User:
        user.deleted_at = None
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def list(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        q: Optional[str] = None,
        role: Optional[str] = None,
        status: Optional[str] = None,
    ) -> tuple[list[User], int]:
        page = normalize_page(page)
        page_size = normalize_page_size(page_size)
        query = db.query(User).filter(User.deleted_at.is_(None))

        if q:
            search = f"%{q}%"
            query = query.filter(
                or_(User.student_no.ilike(search), User.name.ilike(search))
            )

        if role:
            query = query.filter(User.role == role)

        if status:
            query = query.filter(User.status == status)

        total = query.count()
        items = query.order_by(User.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return items, total

    @staticmethod
    def update_last_active(db: Session, user: User) -> None:
        user.last_active_at = local_now()
        db.commit()

    @staticmethod
    def list_active_students(db: Session) -> List[User]:
        """所有未删除、未禁用且角色为 user 的学生（用于通知）"""
        return (
            db.query(User)
            .filter(
                User.deleted_at.is_(None),
                User.status != "disabled",
                User.role == UserRole.STUDENT.value,
            )
            .all()
        )

    @staticmethod
    def count(db: Session, role: Optional[str] = None, status: Optional[str] = None) -> int:
        query = db.query(User).filter(User.deleted_at.is_(None))
        if role:
            query = query.filter(User.role == role)
        if status:
            query = query.filter(User.status == status)
        return query.count()

    @staticmethod
    def set_profile(db: Session, user: User, profile: dict) -> User:
        user.profile = profile
        db.commit()
        db.refresh(user)
        if user.role == UserRole.TEACHER.value:
            from backend.app.services.semantic_service import SemanticService

            SemanticService.refresh_teacher_profile(db, user)
        return user

    @staticmethod
    def list_by_role(db: Session, role: str) -> List[User]:
        return (
            db.query(User)
            .filter(User.deleted_at.is_(None), User.role == role)
            .order_by(User.id.desc())
            .all()
        )
