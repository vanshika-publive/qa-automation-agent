import json
import os
import time
import math
from pathlib import Path

import pytest

PROJECT_ROOT = os.environ.get(
    'PLAYWRIGHT_PROJECT_ROOT',
    str(Path(__file__).resolve().parent.parent),
)
SESSION_PATH = os.path.join(PROJECT_ROOT, '.auth', 'session.json')
SESSION_EXPIRY_SECONDS = 60 * 60 * 24

# Only these cookies actually carry the dashboard login. Transient cookies — Cloudflare's
# __cf_bm (~30 min TTL, regenerated on every request) and analytics (posthog) — must NOT
# invalidate the stored session, or tests run logged-out and fail at the login page.
AUTH_COOKIE_NAMES = {'session', 'publisher_agency'}


def _session_is_valid():
    if not os.path.isfile(SESSION_PATH):
        return False
    try:
        stored = json.loads(Path(SESSION_PATH).read_text(encoding='utf-8'))
        auth_cookies = [c for c in stored.get('cookies', []) if c.get('name') in AUTH_COOKIE_NAMES]
        if not auth_cookies:
            return False
        now = time.time()
        min_expiry = now + 300
        for c in auth_cookies:
            exp = c.get('expires', 0)
            if exp > 0 and exp < min_expiry:
                return False
        return True
    except Exception:
        return False


@pytest.fixture(scope='session')
def browser_type_launch_args():
    headed = os.environ.get('HEADED', '').lower() in ('true', '1', 'yes')
    return {'headless': not headed}


@pytest.fixture(scope='session')
def browser_context_args(browser_context_args):
    args = dict(browser_context_args)
    base_url = os.environ.get('DASHBOARD_URL', 'https://betadashboard.thepublive.com/v2')
    args['base_url'] = base_url

    if _session_is_valid():
        args['storage_state'] = SESSION_PATH

    # Video recording is OFF by default: when a test is interrupted by the pytest-timeout
    # signal mid-action, closing the context to flush the video can hang for many minutes.
    # Enable it only for debugging via RECORD_VIDEO=true.
    if os.environ.get('RECORD_VIDEO', '').lower() in ('true', '1', 'yes'):
        args['record_video_dir'] = os.path.join(PROJECT_ROOT, 'reports', 'videos')
    return args


@pytest.fixture(autouse=True)
def _bounded_timeouts(page):
    """Cap per-action and navigation timeouts so a stuck locator fails well inside the
    30s pytest-timeout budget, allowing a clean failure + teardown instead of a long hang."""
    page.set_default_timeout(15000)
    page.set_default_navigation_timeout(20000)
