from ._base import BASE_PROMPT


def build_prompt(user_input: str) -> str:
    return (
        f"{BASE_PROMPT}\n\n当前任务：代码解释。"
        f"分段解释代码逻辑、分析时间和空间复杂度、指出潜在风险。"
        f"使用 Markdown 代码块和列表格式。"
    )
