import re


def strip_markdown_fences(text: str) -> str:
    return re.sub(r'```[\s\S]*?```', '', text).strip()
