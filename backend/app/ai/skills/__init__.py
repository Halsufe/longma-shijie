"""内置 Skill 的 Prompt 构建器"""
from ._base import BASE_PROMPT
from .mindmap import build_prompt as mindmap_prompt
from .translate import build_prompt as translate_prompt
from .code_explain import build_prompt as code_explain_prompt
from .code_generate import build_prompt as code_generate_prompt
from .summary import build_prompt as summary_prompt
from .polish import build_prompt as polish_prompt
from .db_query import build_prompt as db_query_prompt
from .db_manage import build_prompt as db_manage_prompt
from .competition_recommend import build_prompt as competition_recommend_prompt
from .mentor_match import build_prompt as mentor_match_prompt
from .party_query import build_prompt as party_query_prompt
from .achievement_manage import build_prompt as achievement_manage_prompt

# skill_name -> prompt builder
SKILL_PROMPT_BUILDERS = {
    "mindmap": mindmap_prompt,
    "translate": translate_prompt,
    "code_explain": code_explain_prompt,
    "code_generate": code_generate_prompt,
    "summary": summary_prompt,
    "polish": polish_prompt,
    "db_query": db_query_prompt,
    "db_manage": db_manage_prompt,
    "competition_recommend": competition_recommend_prompt,
    "mentor_match": mentor_match_prompt,
    "party_query": party_query_prompt,
    "achievement_manage": achievement_manage_prompt,
}


def get_skill_prompt(skill_name: str, user_input: str) -> str:
    builder = SKILL_PROMPT_BUILDERS.get(skill_name)
    if builder:
        return builder(user_input)
    return BASE_PROMPT
