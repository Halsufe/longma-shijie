from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.models.achievement import Achievement, AchievementStatus
from backend.app.services.achievement_templates import ACHIEVEMENT_TEMPLATES


router = APIRouter()


@router.get("/stats")
async def get_achievement_stats(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    counts = {category: 0 for category in ACHIEVEMENT_TEMPLATES}
    rows = (
        db.query(Achievement.category, func.count(Achievement.id))
        .filter(
            Achievement.user_id == current_user.id,
            Achievement.status == AchievementStatus.APPROVED,
            Achievement.deleted_at.is_(None),
        )
        .group_by(Achievement.category)
        .all()
    )
    for category, count in rows:
        if category in counts:
            counts[category] = count

    return {
        "class_name": settings.CLASS_NAME,
        "counts": counts,
        "total": sum(counts.values()),
    }
