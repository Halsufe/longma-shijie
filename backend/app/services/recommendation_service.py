"""
个性化推荐服务

基于用户 profile_json（专业、研究方向、技能）推荐：
1. 资源（比赛/经验/资料，按标签和标题匹配）
2. 教师（按研究方向匹配）
3. 成果（公开的高质量成果）

推荐算法：关键词提取 → 标签匹配 → 热度排序
"""
import json
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.app.models.user import User
from backend.app.models.resource import Resource
from backend.app.models.teacher import TeacherDirection
from backend.app.models.achievement import Achievement


class RecommendationService:
    """个性化推荐服务"""

    @staticmethod
    def _extract_keywords(user: User) -> list[str]:
        """从用户 profile_json 提取推荐关键词"""
        keywords: list[str] = []
        if not user.profile_json:
            return keywords
        try:
            profile = json.loads(user.profile_json) if isinstance(user.profile_json, str) else user.profile_json
        except (json.JSONDecodeError, TypeError):
            return keywords

        # 提取专业、研究方向、技能
        for key in ("major", "research", "skills", "field", "directions"):
            val = profile.get(key)
            if isinstance(val, str) and val.strip():
                keywords.append(val.strip())
            elif isinstance(val, list):
                keywords.extend(v.strip() for v in val if isinstance(v, str) and v.strip())
        return keywords

    @staticmethod
    def recommend_resources(
        db: Session, user: User, limit: int = 10,
        resource_type: Optional[str] = None,
    ) -> list[Resource]:
        """
        推荐资源（按用户兴趣匹配标签和标题）

        Args:
            resource_type: 可选过滤（如 competition 只推荐比赛）
        """
        keywords = RecommendationService._extract_keywords(user)
        query = db.query(Resource).filter(
            Resource.deleted_at.is_(None),
            Resource.status == "approved",
        )
        if resource_type:
            query = query.filter(Resource.type == resource_type)

        items = query.order_by(Resource.view_count.desc(), Resource.like_count.desc()).limit(limit * 3).all()

        if not keywords:
            # 无关键词时按热度返回
            return items[:limit]

        # 按关键词匹配度评分
        scored: list[tuple[int, Resource]] = []
        for res in items:
            score = 0
            tags = []
            if res.tags_json:
                try:
                    tags = json.loads(res.tags_json) if isinstance(res.tags_json, str) else res.tags_json
                except (json.JSONDecodeError, TypeError):
                    pass
            for kw in keywords:
                kw_lower = kw.lower()
                # 标签匹配（权重 3）
                for tag in tags:
                    if kw_lower in tag.lower():
                        score += 3
                # 标题匹配（权重 2）
                if kw_lower in res.title.lower():
                    score += 2
            # 热度加分（权重 1）
            score += min(res.view_count // 10, 5) + min(res.like_count, 3)
            scored.append((score, res))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [res for _, res in scored[:limit]]

    @staticmethod
    def recommend_teachers(db: Session, user: User, limit: int = 10) -> list[User]:
        """推荐教师（按研究方向匹配用户兴趣）"""
        keywords = RecommendationService._extract_keywords(user)
        query = db.query(User).filter(
            User.role == "teacher",
            User.deleted_at.is_(None),
            User.status == "active",
        )

        if not keywords:
            return query.order_by(User.id.desc()).limit(limit).all()

        # 查找方向匹配的教师
        teacher_ids: set[int] = set()
        for kw in keywords:
            kw_lower = kw.lower()
            dirs = db.query(TeacherDirection).filter(
                TeacherDirection.deleted_at.is_(None),
                TeacherDirection.is_active.is_(True),
                or_(
                    TeacherDirection.title.ilike(f"%{kw_lower}%"),
                    TeacherDirection.tags_json.ilike(f"%{kw_lower}%"),
                ),
            ).all()
            for d in dirs:
                teacher_ids.add(d.teacher_id)

        if teacher_ids:
            matched = query.filter(User.id.in_(teacher_ids)).all()
            # 不足时补充其他教师
            if len(matched) < limit:
                others = query.filter(~User.id.in_(teacher_ids)).limit(limit - len(matched)).all()
                return matched + others
            return matched[:limit]

        return query.order_by(User.id.desc()).limit(limit).all()

    @staticmethod
    def recommend_achievements(db: Session, user: User, limit: int = 10) -> list[Achievement]:
        """推荐成果（公开的已审核成果，按类别匹配用户兴趣）"""
        keywords = RecommendationService._extract_keywords(user)
        query = db.query(Achievement).filter(
            Achievement.deleted_at.is_(None),
            Achievement.status == "approved",
            Achievement.is_public.is_(True),
        )
        items = query.order_by(Achievement.created_at.desc()).limit(limit * 3).all()

        if not keywords or not items:
            return items[:limit]

        # 按标题匹配度评分
        scored: list[tuple[int, Achievement]] = []
        for ach in items:
            score = 0
            title_lower = ach.title.lower()
            for kw in keywords:
                if kw.lower() in title_lower:
                    score += 2
            scored.append((score, ach))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [ach for _, ach in scored[:limit]]

    @staticmethod
    def get_recommendations(db: Session, user: User, limit: int = 5) -> dict:
        """获取综合推荐（资源+教师+成果）"""
        return {
            "resources": [
                {
                    "id": r.id, "title": r.title, "type": r.type,
                    "tags": json.loads(r.tags_json) if r.tags_json else [],
                    "view_count": r.view_count, "like_count": r.like_count,
                }
                for r in RecommendationService.recommend_resources(db, user, limit)
            ],
            "teachers": [
                {
                    "id": t.id, "name": t.name,
                    "profile": json.loads(t.profile_json) if t.profile_json else None,
                }
                for t in RecommendationService.recommend_teachers(db, user, limit)
            ],
            "achievements": [
                {
                    "id": a.id, "title": a.title, "category": a.category, "level": a.level,
                }
                for a in RecommendationService.recommend_achievements(db, user, limit)
            ],
        }
