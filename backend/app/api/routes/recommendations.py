"""
个性化推荐 API 路由

基于用户 profile 提供资源、教师和成果的个性化推荐。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from backend.app.core.database import get_db
from backend.app.api.deps import get_current_user
from backend.app.services.recommendation_service import RecommendationService

router = APIRouter()


@router.get("/")
async def get_recommendations(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(5, ge=1, le=20),
):
    """获取综合推荐（资源+教师+成果）"""
    return RecommendationService.get_recommendations(db, current_user, limit)


@router.get("/resources")
async def recommend_resources(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(10, ge=1, le=50),
    type: Optional[str] = Query(None, description="资源类型过滤（如 competition）"),
):
    """推荐资源（可按类型过滤，如比赛）"""
    items = RecommendationService.recommend_resources(db, current_user, limit, resource_type=type)
    return {
        "total": len(items),
        "items": [
            {
                "id": r.id, "title": r.title, "type": r.type,
                "tags": __import__("json").loads(r.tags_json) if r.tags_json else [],
                "view_count": r.view_count, "like_count": r.like_count,
                "deadline": r.deadline.isoformat() if r.deadline else None,
                "source": r.source,
            }
            for r in items
        ],
    }


@router.get("/teachers")
async def recommend_teachers(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(10, ge=1, le=50),
):
    """推荐教师（按研究方向匹配）"""
    import json
    items = RecommendationService.recommend_teachers(db, current_user, limit)
    return {
        "total": len(items),
        "items": [
            {
                "id": t.id, "name": t.name, "student_no": t.student_no,
                "profile": json.loads(t.profile_json) if t.profile_json else None,
            }
            for t in items
        ],
    }


@router.get("/achievements")
async def recommend_achievements(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(10, ge=1, le=50),
):
    """推荐成果（公开的已审核成果）"""
    items = RecommendationService.recommend_achievements(db, current_user, limit)
    return {
        "total": len(items),
        "items": [
            {
                "id": a.id, "title": a.title, "category": a.category,
                "level": a.level, "achievement_date": a.achievement_date,
            }
            for a in items
        ],
    }
