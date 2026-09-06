import logging
from typing import Optional

from backend.app.ai.skills import get_skill_prompt, BASE_PROMPT

logger = logging.getLogger(__name__)

# 内置触发词映射（DB 不可用时的兜底）
SKILL_TRIGGERS = {
    "@竞赛推荐": "competition_recommend",
    "@比赛推荐": "competition_recommend",
    "@推荐比赛": "competition_recommend",
    "@competition": "competition_recommend",
    "@导师匹配": "mentor_match",
    "@找导师": "mentor_match",
    "@匹配导师": "mentor_match",
    "@mentor": "mentor_match",
    "@党建查询": "party_query",
    "@党建": "party_query",
    "@党员查询": "party_query",
    "@party": "party_query",
    "@成果管理": "achievement_manage",
    "@我的成果": "achievement_manage",
    "@成果录入": "achievement_manage",
    "@achievement": "achievement_manage",
    "@思维导图": "mindmap",
    "@mindmap": "mindmap",
    "@翻译": "translate",
    "@translate": "translate",
    "@代码解释": "code_explain",
    "@explain": "code_explain",
    "@代码生成": "code_generate",
    "@writecode": "code_generate",
    "@总结": "summary",
    "@summary": "summary",
    "@润色": "polish",
    "@polish": "polish",
    "@查数": "db_query",
    "@db": "db_query",
    "@查询": "db_query",
    "@query": "db_query",
    "@管理": "db_manage",
    "@admin": "db_manage",
    "@系统管理": "db_manage",
}


class SkillDispatcher:
    """Skill 调度器：解析 @技能名 并路由到对应实现"""

    def parse_skill(self, content: str, db=None) -> tuple[Optional[str], str]:
        """
        解析消息中的 Skill 触发词
        db: 可选，传入则从数据库加载启用的触发词映射
        返回: (skill_name, cleaned_content)
        """
        triggers = SKILL_TRIGGERS
        if db is not None:
            try:
                from backend.app.repositories.skill_repo import SkillRepository
                db_map = SkillRepository.get_triggers_map(db)
                triggers = db_map
            except Exception as e:
                logger.warning("Failed to load skill triggers from DB, using fallback: %s", e)

        text = content.strip()
        for trigger, skill_name in triggers.items():
            if text.startswith(trigger):
                cleaned = text[len(trigger):].strip()
                return skill_name, cleaned
        return None, content

    def get_system_prompt(self, skill_name: Optional[str], user_input: str) -> str:
        """根据 Skill 名称返回专用系统提示词"""
        if not skill_name:
            return BASE_PROMPT
        return get_skill_prompt(skill_name, user_input)


skill_dispatcher = SkillDispatcher()
