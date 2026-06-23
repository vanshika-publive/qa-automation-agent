"""Capture a 'Stay signed in' dashboard session that has cleared MFA, and save it to
.auth/session.json for the test runner to reuse.

The dashboard enforces email-OTP MFA, which automated login cannot clear. Run this once
(and again whenever the session expires) to mint a reusable, MFA-cleared session:

    env/bin/python capture_session.py [EnvName]   # EnvName defaults to "Beta"

A browser window opens with email/password pre-filled and "Stay signed in" checked.
Enter the 6-digit OTP from your email, finish signing in, and the session is saved.
"""
import json
import math
import os
import sys
import time
from pathlib import Path

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings  # noqa: E402
from core.models import Environment  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = settings.PLAYWRIGHT_PROJECT_ROOT
SESSION_PATH = os.path.join(ROOT, '.auth', 'session.json')
AUTH_COOKIE_NAMES = ('session', 'publisher_agency')
SESSION_EXPIRY_SECONDS = 60 * 60 * 24

env_name = sys.argv[1] if len(sys.argv) > 1 else 'Beta'
env = Environment.all_objects.filter(name=env_name).first()
if not env:
    raise SystemExit(f'No environment named {env_name!r}')
if not env.login_email or not env.login_password:
    raise SystemExit(f'Environment {env_name!r} has no login credentials set')

print(f'Capturing session for env "{env_name}" ({env.login_email}) at {env.base_url}')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    page.goto(f'{env.base_url}/login', timeout=60000)
    page.get_by_role('textbox', name='Email Address *').fill(env.login_email)
    page.get_by_role('textbox', name='Password *').fill(env.login_password)
    try:
        page.get_by_role('checkbox', name='Stay signed in').check()
    except Exception:
        print('(could not auto-check "Stay signed in" — please tick it manually)')
    page.get_by_role('button', name='Sign In').click()

    print('\n>>> Enter the 6-digit OTP in the browser window and finish signing in.')
    print('>>> Waiting up to 5 minutes for you to reach the dashboard...\n')
    page.wait_for_url(lambda url: '/login' not in url and '/mfa' not in url, timeout=300000)
    page.wait_for_timeout(3000)  # let post-login cookies settle

    os.makedirs(os.path.dirname(SESSION_PATH), exist_ok=True)
    context.storage_state(path=SESSION_PATH)

    stored = json.loads(Path(SESSION_PATH).read_text(encoding='utf-8'))
    far_future = math.floor(time.time()) + SESSION_EXPIRY_SECONDS
    stored['cookies'] = [
        {**c, 'expires': far_future} if c.get('expires') == -1 else c
        for c in stored.get('cookies', [])
    ]
    Path(SESSION_PATH).write_text(json.dumps(stored, indent=2), encoding='utf-8')

    auth = [c['name'] for c in stored.get('cookies', []) if c.get('name') in AUTH_COOKIE_NAMES]
    browser.close()

if auth:
    print(f'\n✅ Saved {SESSION_PATH} — auth cookies captured: {auth}')
else:
    raise SystemExit(
        f'\n❌ Saved {SESSION_PATH} but NO auth cookie was captured. '
        'Did sign-in fully complete (reach the dashboard, not the OTP page)?'
    )
