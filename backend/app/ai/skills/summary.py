from ._base import BASE_PROMPT


def build_prompt(user_input: str) -> str:
    return (
        f"{BASE_PROMPT}\n\n当前任务：文本总结。"
        f"提炼核心要点，用条目式列出关键信息，最后给出一句话总结。"
    )
