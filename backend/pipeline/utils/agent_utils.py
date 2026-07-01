import json
import random
import time
from functools import wraps


class AgentUtils:

    MAX_TOOL_RESULT_CHARS = 8000
    # browser_snapshot on Ant Design pages routinely exceeds 8000 chars just from wrapper divs
    # before reaching later form sections (e.g. Web Story's required image upload lives past
    # char 9700 in a 16000+ char snapshot) — truncating it at the default silently hides those
    # fields from the model, not just from the printed log. Give snapshots a much larger budget.
    MAX_SNAPSHOT_RESULT_CHARS = 24000
    DEFAULT_KEEP_TURNS = 4

    @classmethod
    def retry(cls, max_retries: int = 3):
        """
        Decorator form of call_with_retry.

        Use for wrapping named functions:
            @AgentUtils.retry(max_retries=3)
            def _call_openai():
                return client.chat.completions.create(...)

        For inline lambda calls inside loops (where arguments change per iteration),
        use call_with_retry(lambda: ...) directly — the decorator form requires a
        pre-defined function and cannot capture loop variables as cleanly.
        """
        def decorator(fn):
            @wraps(fn)
            def wrapper(*args, **kwargs):
                return cls.call_with_retry(lambda: fn(*args, **kwargs), max_retries)
            return wrapper
        return decorator

    @staticmethod
    def mcp_to_openai_tool(t: dict) -> dict:
        schema = t.get('inputSchema')
        if not isinstance(schema, dict):
            schema = {'type': 'object', 'properties': {}}
        return {
            'type': 'function',
            'function': {
                'name': t['name'],
                'description': t.get('description', ''),
                'parameters': schema,
            },
        }

    @staticmethod
    def truncate_result(result: str, max_chars: int = None) -> str:
        if max_chars is None:
            max_chars = AgentUtils.MAX_TOOL_RESULT_CHARS
        if len(result) <= max_chars:
            return result
        cut_point = result.rfind('\n', 0, max_chars)
        slice_end = cut_point if cut_point > max_chars * 0.5 else max_chars
        return result[:slice_end] + f'\n...[{len(result) - slice_end} chars truncated]'

    @staticmethod
    def prune_history(messages: list, keep_turns: int = None) -> list:
        if keep_turns is None:
            keep_turns = AgentUtils.DEFAULT_KEEP_TURNS
        header = messages[:2]
        tail = messages[2:]

        turns = []
        cur = []
        for m in tail:
            if m.get('role') == 'assistant':
                if cur:
                    turns.append(cur)
                cur = [m]
            else:
                cur.append(m)
        if cur:
            turns.append(cur)

        kept = turns[-keep_turns:] if len(turns) > keep_turns else turns
        return header + [m for turn in kept for m in turn]

    @staticmethod
    def call_with_retry(fn, max_retries: int = 3):
        for attempt in range(max_retries + 1):
            try:
                return fn()
            except Exception as err:
                if AgentUtils._is_retryable(err) and attempt < max_retries:
                    jitter = random.random() * 2000
                    delay_ms = (attempt + 1) * 15_000 + jitter
                    print(
                        f'Retryable error — retrying in {delay_ms / 1000:.1f}s '
                        f'(attempt {attempt + 1}/{max_retries})...'
                    )
                    time.sleep(delay_ms / 1000)
                    continue
                raise
        raise RuntimeError('call_with_retry: exceeded max retries')

    @staticmethod
    def parse_tool_args(raw: str) -> dict:
        try:
            parsed = json.loads(raw or '{}')
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
        return {}

    @staticmethod
    def _is_retryable(err) -> bool:
        err_str = str(err)
        if '429' in err_str:
            return True
        if hasattr(err, 'status_code') and err.status_code in (429, 502, 503):
            return True
        for code in ('ECONNRESET', 'ETIMEDOUT', 'ECONNREFUSED', 'Connection'):
            if code in err_str:
                return True
        return False
