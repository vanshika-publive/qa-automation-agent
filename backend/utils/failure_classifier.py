import re

# Deterministic (no-LLM) classification of a pytest/Playwright failure message into a
# human-readable category, summary, and the offending locator when one can be recovered.
# Input is the per-test `error` text produced by ExecutionService (prefers crash.message,
# e.g. "TimeoutError: Locator.click: Timeout 15000ms exceeded.\nCall log:\n  - waiting for
# locator(\"tr\").first.get_by_role(\"button\", name=\"Edit\", exact=True)").

UNKNOWN = {'category': 'Test error', 'summary': 'Unknown error', 'locator': None}


def classify_failure(error_text: str) -> dict:
    text = (error_text or '').strip()
    if not text:
        return dict(UNKNOWN)

    low = text.lower()
    locator = _extract_locator(text)

    # A Playwright action timed out waiting for a locator that never appeared.
    if 'timeout' in low and ('waiting for locator' in low or 'waiting for get_by' in low):
        return {
            'category': 'Element not found',
            'summary': (
                'A locator matched no elements before timing out — the selector did not match '
                'anything on the page (the UI changed, or the locator is wrong).'
            ),
            'locator': locator,
        }

    # Locator matched more than one element under Playwright strict mode.
    if 'strict mode violation' in low or 'resolved to' in low:
        return {
            'category': 'Multiple elements matched',
            'summary': (
                'The locator matched more than one element (strict mode). Narrow it with '
                '.first / .nth or a more specific role and name.'
            ),
            'locator': locator,
        }

    # Navigation or URL-wait timed out (page never loaded / never reached expected URL).
    if 'timeout' in low and ('goto' in low or 'wait_for_url' in low or 'navigation' in low):
        return {
            'category': 'Navigation timeout',
            'summary': (
                'A navigation or URL wait timed out — the page did not load or did not reach '
                'the expected URL in time.'
            ),
            'locator': locator,
        }

    # Landed on the login / MFA page — the stored session was invalid or expired.
    if '/mfa' in low or 'capture_session' in low or re.search(r'\b(log ?in|sign ?in)\b', low):
        return {
            'category': 'Session / login',
            'summary': (
                'The run hit the login or MFA page — the stored session is missing or expired. '
                'Re-run capture_session.py to refresh data/.auth/session.json.'
            ),
            'locator': locator,
        }

    # An explicit assertion / expectation failed.
    if 'assertionerror' in low or 'expect(' in low or re.search(r'(^|\n)\s*assert\b', text):
        return {
            'category': 'Assertion failed',
            'summary': _first_line(text),
            'locator': locator,
        }

    # Any other timeout we didn't specifically categorise above.
    if 'timeout' in low:
        return {
            'category': 'Timeout',
            'summary': _first_line(text),
            'locator': locator,
        }

    return {
        'category': 'Test error',
        'summary': _first_line(text),
        'locator': locator,
    }


def _extract_locator(text: str):
    # Playwright call log line: "- waiting for <locator chain>".
    m = re.search(r'waiting for (.+)', text)
    if m:
        return m.group(1).strip()
    # Strict-mode message: "strict mode violation: <locator> resolved to N elements".
    m = re.search(r'strict mode violation:\s*(.+?)\s+resolved to', text)
    if m:
        return m.group(1).strip()
    # A bare locator expression anywhere in the text.
    m = re.search(r'((?:page\.)?(?:locator|get_by_\w+)\([^\n]*)', text)
    if m:
        return m.group(1).strip()
    return None


def _first_line(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line
    return text.strip()
