"""Business Skill executor registry."""

from typing import Final

from backend.app.ai.business_skills.achievement_manage import AchievementManageExecutor
from backend.app.ai.business_skills.base import BusinessSkillExecutor
from backend.app.ai.business_skills.competition_recommend import CompetitionRecommendExecutor
from backend.app.ai.business_skills.mentor_match import MentorMatchExecutor
from backend.app.ai.business_skills.party_query import PartyQueryExecutor


BUSINESS_SKILL_REGISTRY: Final[dict[str, type[BusinessSkillExecutor]]] = {
    CompetitionRecommendExecutor.skill_name: CompetitionRecommendExecutor,
    MentorMatchExecutor.skill_name: MentorMatchExecutor,
    PartyQueryExecutor.skill_name: PartyQueryExecutor,
    AchievementManageExecutor.skill_name: AchievementManageExecutor,
}


__all__ = ["BUSINESS_SKILL_REGISTRY", "BusinessSkillExecutor"]

