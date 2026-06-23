import json
import math
import os
import re
import time
from pathlib import Path

from .credential_manager import get_dashboard_credentials
from .constants import SESSION_EXPIRY_SECONDS, LOGIN_TIMEOUT_MS, LOGIN_PATH

# Cookies that actually carry the dashboard login. Must match conftest's AUTH_COOKIE_NAMES.
AUTH_COOKIE_NAMES = ('session', 'publisher_agency')


def _stored_session_is_valid(session_path):
    """True if .auth/session.json holds a non-expired auth cookie. Transient cookies
    (Cloudflare __cf_bm, analytics) are ignored so they don't force a needless re-login."""
    if not os.path.isfile(session_path):
        return False
    try:
        stored = json.loads(Path(session_path).read_text(encoding='utf-8'))
        auth = [c for c in stored.get('cookies', []) if c.get('name') in AUTH_COOKIE_NAMES]
        if not auth:
            return False
        min_expiry = time.time() + 300
        return all(c.get('expires', 0) <= 0 or c.get('expires', 0) >= min_expiry for c in auth)
    except Exception:
        return False


def _extract_snapshot_ref(snapshot, pattern):
    for line in snapshot.split('\n'):
        if pattern.search(line):
            m = re.search(r'\[ref=([^\]]+)\]', line)
            return m.group(1) if m else None
    return None


def ensure_mcp_authenticated(bridge, base_url):
    creds = get_dashboard_credentials()

    bridge.call_tool('browser_navigate', {'url': base_url})
    snapshot = bridge.call_tool('browser_snapshot', {})

    on_login = (
        bool(re.search(r'sign in|log in|forgot password|enter your (email|password)', snapshot, re.I))
        and not bool(re.search(r'dashboard|posts|article|categories|tags|home', snapshot, re.I))
    )

    if not on_login:
        return

    print('[ensureMCPAuthenticated] MCP browser on login page — logging in via MCP tools')

    bridge.call_tool('browser_navigate', {'url': f'{base_url}/login'})
    login_snapshot = bridge.call_tool('browser_snapshot', {})

    email_target = _extract_snapshot_ref(login_snapshot, re.compile(r'textbox[^\n]*[Ee]mail')) or 'input[type="email"]'
    password_target = _extract_snapshot_ref(login_snapshot, re.compile(r'textbox[^\n]*[Pp]assword')) or 'input[type="password"]'
    signin_target = _extract_snapshot_ref(login_snapshot, re.compile(r'button[^\n]*Sign In')) or 'button[type="submit"]'

    bridge.call_tool('browser_type', {'target': email_target, 'text': creds['dashboard_email']})
    bridge.call_tool('browser_type', {'target': password_target, 'text': creds['dashboard_password']})
    bridge.call_tool('browser_click', {'target': signin_target})

    for _ in range(15):
        time.sleep(1)
        after = bridge.call_tool('browser_snapshot', {})
        still_on_login = (
            bool(re.search(r'sign in|log in|forgot password', after, re.I))
            and not bool(re.search(r'dashboard|posts|article|categories|tags|home', after, re.I))
        )
        if not still_on_login:
            print('[ensureMCPAuthenticated] Login successful')
            return

    raise RuntimeError(
        'MCP browser login timed out — still on login page after 15 s.\n'
        'Check dashboard credentials in your Environment settings.'
    )


def refresh_session(project_root):
    from playwright.sync_api import sync_playwright

    session_path = os.path.join(project_root, '.auth', 'session.json')
    creds = get_dashboard_credentials()

    os.makedirs(os.path.dirname(session_path), exist_ok=True)

    # Reuse strategy: the dashboard requires email-OTP MFA that automated login can't clear,
    # so a manually-created "Stay signed in" session is reused until it expires. If the stored
    # session still has a valid auth cookie, keep it — never clobber it with a fresh login.
    if _stored_session_is_valid(session_path):
        print('Existing session is still valid — reusing it (skipping re-login)')
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        try:
            page.goto(
                f"{creds['dashboard_url']}{LOGIN_PATH}",
                timeout=LOGIN_TIMEOUT_MS,
            )

            email_by_role = page.get_by_role('textbox', name='Email Address *')
            email_by_type = page.locator('input[type="email"]')

            if email_by_role.count():
                email_by_role.fill(creds['dashboard_email'])
            elif email_by_type.count():
                email_by_type.fill(creds['dashboard_email'])
            else:
                page.locator('input[type="text"]').first.fill(creds['dashboard_email'])

            page.get_by_role('textbox', name='Password *').fill(creds['dashboard_password'])
            page.get_by_role('button', name='Sign In').click()
            page.wait_for_url(
                lambda url: not url.endswith(LOGIN_PATH),
                timeout=LOGIN_TIMEOUT_MS,
            )

            # The dashboard enforces email-OTP MFA: email+password redirects to /mfa and NO
            # auth cookie is issued until the 6-digit code is entered. Leaving /login is NOT
            # proof of a successful login. Fail loudly here instead of saving a useless session
            # (which silently makes every downstream test fail at the login page, after the
            # planner/generator have already burned API calls).
            if '/mfa' in page.url:
                raise RuntimeError(
                    'Login requires MFA (an email OTP step) — automated email+password login '
                    'cannot complete it, so no authenticated session was created. '
                    'Reuse a session that already cleared MFA (log in once with "Stay signed in" '
                    'and reuse .auth/session.json), or disable MFA for the automation account.'
                )

            context.storage_state(path=session_path)

            # Final guard: a real auth cookie must exist, or downstream tests run logged out.
            check = json.loads(Path(session_path).read_text(encoding='utf-8'))
            if not any(c.get('name') in ('session', 'publisher_agency')
                       for c in check.get('cookies', [])):
                raise RuntimeError(
                    'Login completed but no auth cookie (session / publisher_agency) was '
                    'captured — the login flow likely changed (e.g. MFA). Not saving a broken session.'
                )

            stored = json.loads(Path(session_path).read_text(encoding='utf-8'))
            far_future = math.floor(time.time()) + SESSION_EXPIRY_SECONDS
            stored['cookies'] = [
                {**c, 'expires': far_future} if c.get('expires') == -1 else c
                for c in stored.get('cookies', [])
            ]
            Path(session_path).write_text(json.dumps(stored, indent=2), encoding='utf-8')
            print(f'Session saved to {session_path}')
        finally:
            browser.close()
