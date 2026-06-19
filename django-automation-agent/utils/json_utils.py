import json
from typing import Any


def safe_json_parse(raw: str, default: Any = None) -> Any:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default
