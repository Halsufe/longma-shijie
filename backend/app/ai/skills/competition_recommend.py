"""Prompt builder for the competition recommendation business Skill."""

from ._base import BASE_PROMPT


def build_prompt(user_input: str) -> str:
    return f"""{BASE_PROMPT}

## 当前业务 Skill：竞赛推荐

用户需求：{user_input}

请结合用户画像、对话补充条件和系统返回的已审核比赛候选进行推荐。过滤已截止比赛；每条结果应包含比赛名称、标签、来源、截止时间和明确的推荐理由。不得编造比赛或返回待审核、已拒绝的比赛。若候选不足，应如实说明。"""
