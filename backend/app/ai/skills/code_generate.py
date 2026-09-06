from ._base import BASE_PROMPT


def build_prompt(user_input: str) -> str:
    return (
        f"{BASE_PROMPT}\n\n当前任务：代码生成。"
        f"根据描述生成代码，使用带语言标识的 Markdown 代码块。"
        f"代码后附简要说明。"
    )
