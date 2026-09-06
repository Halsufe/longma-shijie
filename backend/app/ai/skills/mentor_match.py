"""Prompt builder for the mentor matching business Skill."""

from ._base import BASE_PROMPT


def build_prompt(user_input: str) -> str:
    return f"""{BASE_PROMPT}

## 当前业务 Skill：导师匹配

用户提供的项目描述：{user_input}

请根据项目描述与教师有效研究方向的匹配结果推荐导师。每条结果应包含教师姓名、研究方向、匹配点和推荐理由，不得泄露联系方式等非授权信息。若项目描述不足以完成可靠匹配，应引导用户补充研究目标、技术路线或关键词。"""
