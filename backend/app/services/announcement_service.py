from datetime import date
from sqlalchemy.orm import Session

from backend.app.repositories.announcement_repo import AnnouncementRepository


class AnnouncementService:
    @staticmethod
    def list_for_user(db: Session, **filters):
        return AnnouncementRepository.list_visible(db, **filters)

    @staticmethod
    def sources(db: Session):
        return AnnouncementRepository.list_sources(db, enabled_only=True)

