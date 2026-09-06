from typing import Optional, List
from datetime import datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.models.teacher import TeacherDirection, CommunicationApplication, LearningPlan
from backend.app.models.user import User
from backend.app.core.pagination import normalize_page, normalize_page_size
from backend.app.core.database import local_now


class TeacherRepository:
    # --- Teacher Directions ---

    @staticmethod
    def create_direction(db: Session, teacher_id: int, **kwargs) -> TeacherDirection:
        d = TeacherDirection(teacher_id=teacher_id, **kwargs)
        db.add(d)
        db.commit()
        db.refresh(d)
        TeacherRepository._refresh_direction_embedding(db, d)
        return d

    @staticmethod
    def get_direction(db: Session, direction_id: int) -> Optional[TeacherDirection]:
        return db.query(TeacherDirection).filter(TeacherDirection.id == direction_id, TeacherDirection.deleted_at.is_(None)).first()

    @staticmethod
    def update_direction(db: Session, direction: TeacherDirection, **kwargs) -> TeacherDirection:
        for key, value in kwargs.items():
            if hasattr(direction, key) and value is not None:
                setattr(direction, key, value)
        db.commit()
        db.refresh(direction)
        TeacherRepository._refresh_direction_embedding(db, direction)
        return direction

    @staticmethod
    def soft_delete_direction(db: Session, direction: TeacherDirection) -> None:
        direction.deleted_at = local_now()
        db.commit()
        TeacherRepository._refresh_direction_embedding(db, direction)

    @staticmethod
    def _refresh_direction_embedding(db: Session, direction: TeacherDirection) -> None:
        from backend.app.services.semantic_service import SemanticService

        SemanticService.refresh_teacher_direction(db, direction)

    @staticmethod
    def list_by_teacher(db: Session, teacher_id: int, active_only: bool = False) -> List[TeacherDirection]:
        query = db.query(TeacherDirection).filter(TeacherDirection.teacher_id == teacher_id, TeacherDirection.deleted_at.is_(None))
        if active_only:
            query = query.filter(TeacherDirection.is_active.is_(True))
        return query.order_by(TeacherDirection.created_at.desc()).all()

    # --- Teacher Matching ---

    @staticmethod
    def get_teacher(db: Session, teacher_id: int) -> Optional[User]:
        return db.query(User).filter(User.id == teacher_id, User.role == "teacher", User.deleted_at.is_(None)).first()

    @staticmethod
    def match_teachers(
        db: Session, q: Optional[str] = None, tag: Optional[str] = None,
        page: int = 1, page_size: int = 20,
    ) -> tuple[List[User], int]:
        page = normalize_page(page)
        page_size = normalize_page_size(page_size)
        query = db.query(User).filter(User.role == "teacher", User.deleted_at.is_(None))
        if q:
            search = f"%{q}%"
            direction_ids = [d.teacher_id for d in db.query(TeacherDirection).filter(
                TeacherDirection.title.ilike(search), TeacherDirection.deleted_at.is_(None)
            ).all()]
            query = query.filter(or_(User.name.ilike(search), User.id.in_(direction_ids)))
        if tag:
            direction_ids = [d.teacher_id for d in db.query(TeacherDirection).filter(
                TeacherDirection.tags_json.contains(tag), TeacherDirection.deleted_at.is_(None)
            ).all()]
            query = query.filter(User.id.in_(direction_ids))
        total = query.count()
        items = query.order_by(User.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return items, total

    # --- Communication Applications ---

    @staticmethod
    def create_application(db: Session, student_id: int, **kwargs) -> CommunicationApplication:
        app = CommunicationApplication(student_id=student_id, **kwargs)
        db.add(app)
        db.commit()
        db.refresh(app)
        return app

    @staticmethod
    def get_application(db: Session, app_id: int) -> Optional[CommunicationApplication]:
        return db.query(CommunicationApplication).filter(CommunicationApplication.id == app_id, CommunicationApplication.deleted_at.is_(None)).first()

    @staticmethod
    def update_application_status(db: Session, app: CommunicationApplication, status: str) -> CommunicationApplication:
        app.status = status
        app.decided_at = local_now()
        db.commit()
        db.refresh(app)
        return app

    @staticmethod
    def soft_delete_application(db: Session, app: CommunicationApplication) -> None:
        app.deleted_at = local_now()
        db.commit()

    @staticmethod
    def list_applications_by_student(
        db: Session, student_id: int, page: int = 1, page_size: int = 20,
        status: Optional[str] = None,
    ) -> tuple[List[CommunicationApplication], int]:
        page = normalize_page(page)
        page_size = normalize_page_size(page_size)
        query = db.query(CommunicationApplication).filter(
            CommunicationApplication.student_id == student_id, CommunicationApplication.deleted_at.is_(None)
        )
        if status:
            query = query.filter(CommunicationApplication.status == status)
        total = query.count()
        items = query.order_by(CommunicationApplication.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return items, total

    @staticmethod
    def list_applications_by_teacher(
        db: Session, teacher_id: int, page: int = 1, page_size: int = 20,
        status: Optional[str] = None,
    ) -> tuple[List[CommunicationApplication], int]:
        page = normalize_page(page)
        page_size = normalize_page_size(page_size)
        query = db.query(CommunicationApplication).filter(
            CommunicationApplication.teacher_id == teacher_id, CommunicationApplication.deleted_at.is_(None)
        )
        if status:
            query = query.filter(CommunicationApplication.status == status)
        total = query.count()
        items = query.order_by(CommunicationApplication.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return items, total

    # --- Learning Plans ---

    @staticmethod
    def create_plan(db: Session, user_id: int, **kwargs) -> LearningPlan:
        plan = LearningPlan(user_id=user_id, **kwargs)
        db.add(plan)
        db.commit()
        db.refresh(plan)
        return plan

    @staticmethod
    def get_plan(db: Session, plan_id: int) -> Optional[LearningPlan]:
        return db.query(LearningPlan).filter(LearningPlan.id == plan_id, LearningPlan.deleted_at.is_(None)).first()

    @staticmethod
    def update_plan(db: Session, plan: LearningPlan, **kwargs) -> LearningPlan:
        for key, value in kwargs.items():
            if hasattr(plan, key) and value is not None:
                setattr(plan, key, value)
        db.commit()
        db.refresh(plan)
        return plan

    @staticmethod
    def soft_delete_plan(db: Session, plan: LearningPlan) -> None:
        plan.deleted_at = local_now()
        db.commit()

    @staticmethod
    def list_plans(
        db: Session, user_id: int, page: int = 1, page_size: int = 20,
        is_completed: Optional[bool] = None,
    ) -> tuple[List[LearningPlan], int]:
        page = normalize_page(page)
        page_size = normalize_page_size(page_size)
        query = db.query(LearningPlan).filter(LearningPlan.user_id == user_id, LearningPlan.deleted_at.is_(None))
        if is_completed is not None:
            query = query.filter(LearningPlan.is_completed == is_completed)
        total = query.count()
        items = query.order_by(LearningPlan.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return items, total
