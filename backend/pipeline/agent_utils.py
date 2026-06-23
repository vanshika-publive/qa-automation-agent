import json
import random
import time

MAX_TOOL_RESULT_CHARS = 8000
DEFAULT_KEEP_TURNS = 4


def mcp_to_openai_tool(t):
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


def truncate_result(result, max_chars=MAX_TOOL_RESULT_CHARS):
    if len(result) <= max_chars:
        return result
    cut_point = result.rfind('\n', 0, max_chars)
    slice_end = cut_point if cut_point > max_chars * 0.5 else max_chars
    return result[:slice_end] + f'\n...[{len(result) - slice_end} chars truncated]'


def prune_history(messages, keep_turns=DEFAULT_KEEP_TURNS):
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
    flat = [m for turn in kept for m in turn]
    return header + flat


def _is_retryable(err):
    err_str = str(err)
    if '429' in err_str:
        return True
    if hasattr(err, 'status_code'):
        if err.status_code in (429, 502, 503):
            return True
    for code in ('ECONNRESET', 'ETIMEDOUT', 'ECONNREFUSED', 'Connection'):
        if code in err_str:
            return True
    return False


def call_with_retry(fn, max_retries=3):
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except Exception as err:
            if _is_retryable(err) and attempt < max_retries:
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


def parse_tool_args(raw):
    try:
        parsed = json.loads(raw or '{}')
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    return {}
