from ._base import BASE_PROMPT


def build_prompt(user_input: str) -> str:
    return (
        f"{BASE_PROMPT}\n\n当前任务：翻译。"
        f"自动检测输入语言：中文翻译为英文，其他语言翻译为中文。"
        f"只输出翻译结果，不要解释。"
    )
