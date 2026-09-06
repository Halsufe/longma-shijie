from datetime import datetime

from sqlalchemy.orm import Session

from backend.app.core.database import local_now
from backend.app.models.user import AlumniConversionRequest, User


class AlumniConversionService:
    @staticmethod
    def request(db: Session, user: User, graduation_year: int) -> AlumniConversionRequest:
        now_year = local_now().year
        if user.role != "student" or user.status != "active":
            raise ValueError("仅启用中的在校学生可申请")
        if graduation_year < 1950 or graduation_year > now_year:
            raise ValueError("毕业年份必须在 1950 至当前年份之间")
        existing = (
            db.query(AlumniConversionRequest)
            .filter(
                AlumniConversionRequest.user_id == user.id,
                AlumniConversionRequest.status == "pending",
            )
            .first()
        )
        if existing:
            raise ValueError("已有待审核申请")
        item = AlumniConversionRequest(user_id=user.id, graduation_year=graduation_year)
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def convert(db: Session, user: User, graduation_year: int, reviewer_id: int | None = None) -> User:
        if graduation_year < 1950 or graduation_year > local_now().year:
            raise ValueError("毕业年份无效")
        user.role = "alumni"
        user.graduation_year = graduation_year
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def review(
        db: Session, item: AlumniConversionRequest, reviewer: User, approve: bool, comment: str | None = None
    ) -> User:
        if item.status != "pending":
            raise ValueError("申请已处理")
        user = db.query(User).filter(User.id == item.user_id).first()
        if not user:
            raise ValueError("用户不存在")
        item.status = "approved" if approve else "rejected"
        item.review_comment = comment
        item.reviewed_by = reviewer.id
        item.reviewed_at = local_now()
        if approve:
            user.role = "alumni"
            user.graduation_year = item.graduation_year
        db.commit()
        db.refresh(user)
        return user
