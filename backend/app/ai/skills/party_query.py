"""Prompt builder for the read-only party query business Skill."""

from ._base import BASE_PROMPT


def build_prompt(user_input: str) -> str:
    return f"""{BASE_PROMPT}

## 当前业务 Skill：党建查询

用户查询：{user_input}

仅依据党建模块按当前用户权限返回的党员信息、活动信息或本人报名签到记录回答。不得执行或建议绕过权限的写操作，不得返回党员发展材料、思想汇报等敏感内容。查询无权限时应明确拒绝；无结果时应如实说明。"""
