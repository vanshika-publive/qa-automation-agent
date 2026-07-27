import json
import random
import re
import threading
import time
from functools import wraps

from pipeline.constants import (
    AI_PRICE_INPUT_PER_M,
    AI_PRICE_CACHED_INPUT_PER_M,
    AI_PRICE_OUTPUT_PER_M,
)

_thread_api_calls = threading.local()


class AgentUtils:

    MAX_TOOL_RESULT_CHARS = 8000
    # Ant Design snapshots routinely exceed 8000 chars before reaching later form sections;
    # truncating at the default silently hides fields from the model. Give snapshots a larger budget.
    MAX_SNAPSHOT_RESULT_CHARS = 24000
    DEFAULT_KEEP_TURNS = 4

    # Ant Design portals overlays (modals, popovers, dropdowns, menus) to the END of the DOM,
    # so on a content-heavy page they serialize past every truncation budget and become invisible
    # to the model even though the overlay is exactly what the preceding click just opened.
    OVERLAY_ROLES = ('dialog', 'alertdialog', 'menu', 'menubar', 'listbox', 'tooltip')
    _OVERLAY_HEADER = re.compile(
        r'^(\s*)-\s+(' + '|'.join(OVERLAY_ROLES) + r')\b'
    )

    @classmethod
    def retry(cls, max_retries: int = 3):
        """Decorator form of call_with_retry. Use for wrapping named functions.

        For inline lambdas in loops, use call_with_retry(lambda: ...) directly --
        the decorator can't capture loop variables as cleanly.
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
    def surface_overlays(result: str) -> str:
        """Lift any overlay subtree (modal / popover / dropdown / menu) to the front of an aria
        snapshot so fixed-size truncation cannot hide it.

        Portaled overlays render last in the DOM; on a content-heavy page they fall past every
        truncation budget and the model never sees the option it just opened. Copies each overlay
        block above the full tree under a banner so it survives truncation. No-op when no overlay
        role is present, so normal snapshots are byte-identical.
        """
        if not result or '- ' not in result:
            return result
        lines = result.split('\n')
        n = len(lines)
        blocks = []
        i = 0
        while i < n:
            m = AgentUtils._OVERLAY_HEADER.match(lines[i])
            if not m:
                i += 1
                continue
            indent = len(m.group(1))
            block = [lines[i]]
            j = i + 1
            while j < n:
                line = lines[j]
                if line.strip() and (len(line) - len(line.lstrip())) <= indent:
                    break
                block.append(line)
                j += 1
            blocks.append('\n'.join(block).rstrip())
            i = j
        if not blocks:
            return result
        banner = (
            '### ACTIVE OVERLAY — a modal/popover/menu/dropdown is open (usually opened by the '
            'click you just made). Act on it first: click the option/button inside it you need. '
            'Its options appear ONLY here, not in the sidebar or main page below.'
        )
        return banner + '\n' + '\n\n'.join(blocks) + '\n\n### Full page snapshot:\n' + result

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
    def reset_call_counter():
        _thread_api_calls.count = 0
        _thread_api_calls.prompt_tokens = 0
        _thread_api_calls.completion_tokens = 0
        _thread_api_calls.cached_tokens = 0

    @staticmethod
    def get_call_count() -> int:
        return getattr(_thread_api_calls, 'count', 0)

    @staticmethod
    def _accumulate_tokens(usage) -> None:
        if usage is None:
            return
        _thread_api_calls.prompt_tokens = getattr(_thread_api_calls, 'prompt_tokens', 0) + (usage.prompt_tokens or 0)
        _thread_api_calls.completion_tokens = getattr(_thread_api_calls, 'completion_tokens', 0) + (usage.completion_tokens or 0)
        details = getattr(usage, 'prompt_tokens_details', None)
        _thread_api_calls.cached_tokens = getattr(_thread_api_calls, 'cached_tokens', 0) + (getattr(details, 'cached_tokens', 0) or 0)

    @staticmethod
    def get_token_summary() -> str:
        calls = getattr(_thread_api_calls, 'count', 0)
        prompt = getattr(_thread_api_calls, 'prompt_tokens', 0)
        completion = getattr(_thread_api_calls, 'completion_tokens', 0)
        cached = getattr(_thread_api_calls, 'cached_tokens', 0)
        cache_pct = f' ({cached * 100 // prompt}% hit)' if prompt > 0 and cached > 0 else ''
        return (
            f'calls={calls}  prompt={prompt:,}{cache_pct}  cached={cached:,}  '
            f'completion={completion:,}  total={prompt + completion:,}'
        )

    @staticmethod
    def token_cost_usd(prompt: int, cached: int, completion: int) -> float:
        # cached is a subset of prompt; the uncached remainder bills at the full input rate.
        uncached = max(prompt - cached, 0)
        cost = (
            uncached * AI_PRICE_INPUT_PER_M
            + cached * AI_PRICE_CACHED_INPUT_PER_M
            + completion * AI_PRICE_OUTPUT_PER_M
        ) / 1_000_000
        return round(cost, 6)

    @staticmethod
    def get_token_totals() -> dict:
        prompt = getattr(_thread_api_calls, 'prompt_tokens', 0)
        cached = getattr(_thread_api_calls, 'cached_tokens', 0)
        completion = getattr(_thread_api_calls, 'completion_tokens', 0)
        return {
            'prompt_tokens': prompt,
            'cached_tokens': cached,
            'completion_tokens': completion,
            'cost_usd': AgentUtils.token_cost_usd(prompt, cached, completion),
        }

    @staticmethod
    def record_usage(usage) -> None:
        # For single-shot callers (e.g. the orchestrator) that don't go through call_with_retry:
        # count the call and fold its usage into the thread-local totals.
        _thread_api_calls.count = getattr(_thread_api_calls, 'count', 0) + 1
        AgentUtils._accumulate_tokens(usage)

    @staticmethod
    def call_with_retry(fn, max_retries: int = 3):
        for attempt in range(max_retries + 1):
            try:
                result = fn()
                _thread_api_calls.count = getattr(_thread_api_calls, 'count', 0) + 1
                AgentUtils._accumulate_tokens(getattr(result, 'usage', None))
                return result
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
