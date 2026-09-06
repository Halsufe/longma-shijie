from sqlalchemy import extract, or_
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session

from backend.app.core.database import local_now
from backend.app.core.pagination import normalize_page, normalize_page_size
from backend.app.models.party import (
    PartyActivity,
    PartyActivityParticipant,
    PartyMaterial,
    PoliticalStatusReview,
)
from backend.app.models.user import User, UserRole


class PartyRepository:
    @staticmethod
    def get_user(db: Session, user_id: int) -> User | None:
        return (
            db.query(User)
            .filter(User.id == user_id, User.deleted_at.is_(None))
            .first()
        )

    @staticmethod
    def get_member(db: Session, user_id: int) -> User | None:
        return (
            db.query(User)
            .filter(
                User.id == user_id,
                User.role == UserRole.STUDENT.value,
                User.deleted_at.is_(None),
            )
            .first()
        )

    @staticmethod
    def get_user_by_student_no(db: Session, student_no: str) -> User | None:
        return (
            db.query(User)
            .filter(
                User.student_no == student_no.strip(),
                User.role == UserRole.STUDENT.value,
                User.deleted_at.is_(None),
            )
            .first()
        )

    @staticmethod
    def list_members(
        db: Session,
        *,
        class_name: str | None = None,
        party_type: str | None = None,
        apply_status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[User], int, int, int]:
        normalized_page = normalize_page(page)
        normalized_size = normalize_page_size(page_size)
        users = (
            db.query(User)
            .filter(
                User.role == UserRole.STUDENT.value,
                User.deleted_at.is_(None),
            )
            .order_by(User.id.desc())
            .all()
        )
        members = []
        for user in users:
            party = user.party
            if not party.get("party_type") or party.get("deleted_at"):
                continue
            if class_name and party.get("class_name") != class_name:
                continue
            if party_type and party.get("party_type") != party_type:
                continue
            if apply_status and party.get("apply_status") != apply_status:
                continue
            members.append(user)
        total = len(members)
        start = (normalized_page - 1) * normalized_size
        return (
            members[start : start + normalized_size],
            total,
            normalized_page,
            normalized_size,
        )

    @staticmethod
    def set_profile(db: Session, user: User, profile: dict) -> User:
        user.party = profile
        db.add(user)
        return user

    @staticmethod
    def create_material(db: Session, **values) -> PartyMaterial:
        material = PartyMaterial(**values)
        db.add(material)
        return material

    @staticmethod
    def get_material(db: Session, material_id: int) -> PartyMaterial | None:
        return (
            db.query(PartyMaterial)
            .filter(
                PartyMaterial.id == material_id,
                PartyMaterial.deleted_at.is_(None),
            )
            .first()
        )

    @staticmethod
    def list_materials(db: Session, user_id: int) -> list[PartyMaterial]:
        return (
            db.query(PartyMaterial)
            .filter(
                PartyMaterial.user_id == user_id,
                PartyMaterial.deleted_at.is_(None),
            )
            .order_by(PartyMaterial.uploaded_at.desc(), PartyMaterial.id.desc())
            .all()
        )

    @staticmethod
    def soft_delete_material(db: Session, material: PartyMaterial) -> PartyMaterial:
        material.deleted_at = local_now()
        db.add(material)
        return material

    @staticmethod
    def create_activity(db: Session, **values) -> PartyActivity:
        activity = PartyActivity(**values)
        db.add(activity)
        return activity

    @staticmethod
    def get_activity(db: Session, activity_id: int) -> PartyActivity | None:
        return (
            db.query(PartyActivity)
            .filter(
                PartyActivity.id == activity_id,
                PartyActivity.deleted_at.is_(None),
            )
            .first()
        )

    @staticmethod
    def query_activities(
        db: Session,
        *,
        status: str | None = None,
        category: str | None = None,
        year: int | None = None,
    ) -> list[PartyActivity]:
        query = db.query(PartyActivity).filter(PartyActivity.deleted_at.is_(None))
        if status:
            query = query.filter(PartyActivity.status == status)
        if category:
            query = query.filter(PartyActivity.category == category)
        if year is not None:
            query = query.filter(extract("year", PartyActivity.start_at) == year)
        return query.order_by(PartyActivity.start_at.desc(), PartyActivity.id.desc()).all()

    @staticmethod
    def soft_delete_activity(
        db: Session, activity: PartyActivity
    ) -> PartyActivity:
        activity.deleted_at = local_now()
        db.add(activity)
        return activity

    @staticmethod
    def get_participant(
        db: Session, activity_id: int, user_id: int
    ) -> PartyActivityParticipant | None:
        return (
            db.query(PartyActivityParticipant)
            .filter(
                PartyActivityParticipant.activity_id == activity_id,
                PartyActivityParticipant.user_id == user_id,
            )
            .first()
        )

    @staticmethod
    def create_participant(
        db: Session, *, activity_id: int, user_id: int
    ) -> PartyActivityParticipant:
        participant = PartyActivityParticipant(
            activity_id=activity_id,
            user_id=user_id,
        )
        db.add(participant)
        return participant

    @staticmethod
    def count_registered(db: Session, activity_id: int) -> int:
        return (
            db.query(PartyActivityParticipant)
            .filter(
                PartyActivityParticipant.activity_id == activity_id,
                PartyActivityParticipant.registration_status == "registered",
            )
            .count()
        )

    @staticmethod
    def list_user_participants(
        db: Session, user_id: int
    ) -> list[Row[tuple[PartyActivityParticipant, PartyActivity]]]:
        return (
            db.query(PartyActivityParticipant, PartyActivity)
            .join(PartyActivity, PartyActivity.id == PartyActivityParticipant.activity_id)
            .filter(
                PartyActivityParticipant.user_id == user_id,
                PartyActivity.deleted_at.is_(None),
            )
            .order_by(PartyActivity.start_at.desc(), PartyActivityParticipant.id.desc())
            .all()
        )

    @staticmethod
    def list_activity_participants(
        db: Session, activity_id: int
    ) -> list[PartyActivityParticipant]:
        return (
            db.query(PartyActivityParticipant)
            .filter(PartyActivityParticipant.activity_id == activity_id)
            .order_by(PartyActivityParticipant.id)
            .all()
        )

    @staticmethod
    def list_users_by_ids(db: Session, user_ids: list[int]) -> list[User]:
        if not user_ids:
            return []
        return (
            db.query(User)
            .filter(User.id.in_(user_ids), User.deleted_at.is_(None))
            .all()
        )

    @staticmethod
    def list_active_users(db: Session) -> list[User]:
        return (
            db.query(User)
            .filter(User.status == "active", User.deleted_at.is_(None))
            .order_by(User.id)
            .all()
        )

    @staticmethod
    def list_active_materials(db: Session) -> list[PartyMaterial]:
        return (
            db.query(PartyMaterial)
            .filter(PartyMaterial.deleted_at.is_(None))
            .order_by(PartyMaterial.uploaded_at.desc(), PartyMaterial.id.desc())
            .all()
        )

    @staticmethod
    def create_political_review(
        db: Session, **values
    ) -> PoliticalStatusReview:
        review = PoliticalStatusReview(**values)
        db.add(review)
        return review

    @staticmethod
    def get_political_review(
        db: Session, review_id: int
    ) -> PoliticalStatusReview | None:
        return db.query(PoliticalStatusReview).filter(
            PoliticalStatusReview.id == review_id
        ).first()

    @staticmethod
    def latest_political_review(
        db: Session, user_id: int
    ) -> PoliticalStatusReview | None:
        return (
            db.query(PoliticalStatusReview)
            .filter(PoliticalStatusReview.user_id == user_id)
            .order_by(
                PoliticalStatusReview.submitted_at.desc(),
                PoliticalStatusReview.id.desc(),
            )
            .first()
        )

    @staticmethod
    def pending_political_review(
        db: Session, user_id: int
    ) -> PoliticalStatusReview | None:
        return (
            db.query(PoliticalStatusReview)
            .filter(
                PoliticalStatusReview.user_id == user_id,
                PoliticalStatusReview.status == "pending",
            )
            .order_by(PoliticalStatusReview.id.desc())
            .first()
        )

    @staticmethod
    def list_political_reviews(
        db: Session,
        *,
        status: str | None = None,
        user_id: int | None = None,
        to_status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[PoliticalStatusReview], int, int, int]:
        normalized_page = normalize_page(page)
        normalized_size = normalize_page_size(page_size)
        query = db.query(PoliticalStatusReview)
        if status:
            query = query.filter(PoliticalStatusReview.status == status)
        if user_id is not None:
            query = query.filter(PoliticalStatusReview.user_id == user_id)
        if to_status:
            query = query.filter(PoliticalStatusReview.to_status == to_status)
        total = query.count()
        items = (
            query.order_by(
                PoliticalStatusReview.submitted_at.desc(),
                PoliticalStatusReview.id.desc(),
            )
            .offset((normalized_page - 1) * normalized_size)
            .limit(normalized_size)
            .all()
        )
        return items, total, normalized_page, normalized_size

    @staticmethod
    def list_political_roster(
        db: Session,
        *,
        q: str | None = None,
        political_status: str | None = None,
        class_name: str | None = None,
        grade: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[User], int, int, int]:
        normalized_page = normalize_page(page)
        normalized_size = normalize_page_size(page_size)
        query = db.query(User).filter(
            User.role == UserRole.STUDENT.value,
            User.deleted_at.is_(None),
        )
        if q:
            search = f"%{q.strip()}%"
            query = query.filter(or_(User.student_no.ilike(search), User.name.ilike(search)))
        if political_status:
            query = query.filter(User.political_status == political_status)

        users = query.order_by(User.id.desc()).all()
        filtered = []
        for user in users:
            party = user.party
            profile = user.profile
            user_class = party.get("class_name") or profile.get("class_name")
            user_grade = party.get("grade") or profile.get("grade")
            if class_name and user_class != class_name:
                continue
            if grade and user_grade != grade:
                continue
            filtered.append(user)
        total = len(filtered)
        start = (normalized_page - 1) * normalized_size
        return (
            filtered[start : start + normalized_size],
            total,
            normalized_page,
            normalized_size,
        )
