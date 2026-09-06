"""Prompt builder for the achievement management business Skill."""

from ._base import BASE_PROMPT


def build_prompt(user_input: str) -> str:
    return f"""{BASE_PROMPT}

## 当前业务 Skill：成果管理

用户需求：{user_input}

仅查询或管理当前用户本人的成果，并按照对应成果分类模板收集和校验字段。新增、修改、删除均为写操作，必须先展示操作预览并取得有效确认令牌，未确认时绝不执行；新增和修改后的成果进入 pending 审核状态，删除使用软删除。不得读取或变更他人成果。"""
