import json
import random
import re
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

    # Roles that denote a transient overlay layered over the page: modals, popovers, dropdown
    # option lists, context/create menus, tooltips-as-menus. React (Ant Design) portals these to
    # the END of the DOM, so on a content-heavy page (large table/list) they serialize hundreds
    # of lines down — past every truncation budget — and become invisible to the model even
    # though the overlay is the exact thing a preceding click just opened and must act on.
    # Confirmed 2026-07-08: the Custom Content "Blank Canvas" create option sits at char ~40,289
    # of a 41,208-char snapshot, cut by both the 8000 (click) and 24000 (snapshot) limits.
    OVERLAY_ROLES = ('dialog', 'alertdialog', 'menu', 'menubar', 'listbox', 'tooltip')
    _OVERLAY_HEADER = re.compile(
        r'^(\s*)-\s+(' + '|'.join(OVERLAY_ROLES) + r')\b'
    )

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
    def surface_overlays(result: str) -> str:
        """Lift any overlay subtree (modal / popover / dropdown / menu) to the front of an aria
        snapshot so fixed-size truncation cannot hide it.

        Portaled overlays render last in the DOM and therefore last in the snapshot; on a big
        page they fall past the truncation cliff and the model never sees the option it just
        opened (e.g. clicking Custom Content's "Create" opens a popover whose "Blank Canvas"
        entry is ~32k chars past the 8000-char click-result limit — so the planner looped and
        fell back to a hallucinated plan). This copies each overlay block above the full tree,
        under a banner, so it survives truncation and the model acts on it.

        No-op (returns the input unchanged) when the text contains no overlay role — the common
        case — so normal snapshots and non-snapshot tool results are byte-identical.
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
