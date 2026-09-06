from ._base import BASE_PROMPT


def build_prompt(user_input: str) -> str:
    return (
        f"{BASE_PROMPT}\n\n当前任务：文本润色。"
        f"优化语言表达，保持原意，提升流畅度和专业性。"
        f"先给出润色后的文本，再用要点列出主要修改。"
    )
