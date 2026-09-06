from ._base import BASE_PROMPT


def build_prompt(user_input: str) -> str:
    return (
        f"{BASE_PROMPT}\n\n当前任务：思维导图生成。"
        f"请将用户输入的内容整理为 Markdown 大纲格式，使用 # ## ### 表示层级。"
        f"输出格式：先一段简短说明，然后给出 Markdown 大纲。"
    )
