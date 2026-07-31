import json
import os
import time
import math
from pathlib import Path

import pytest

# data/ dir — runtime artifacts (generated tests, session, reports)
PROJECT_ROOT = os.environ.get(
    'PLAYWRIGHT_PROJECT_ROOT',
    str(Path(__file__).resolve().parent.parent),
)
# backend/ dir — source code, pipeline package; set by runner.py or dev's shell
BACKEND_ROOT = os.environ.get(
    'BACKEND_ROOT',
    str(Path(__file__).resolve().parent.parent.parent / 'backend'),
)
SESSION_PATH = os.path.join(PROJECT_ROOT, '.auth', 'session.json')
SESSION_EXPIRY_SECONDS = 60 * 60 * 24
DASHBOARD_URL = os.environ.get('DASHBOARD_URL', 'https://betadashboard.thepublive.com/v2')

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
def browser_type_launch_args(browser_type_launch_args):
    headed = os.environ.get('HEADED', '').lower() in ('true', '1', 'yes')
    # playwright-core already adds --no-sandbox (its default when chromiumSandbox isn't forced on)
    # and --disable-dev-shm-usage to its default chromium switches, so the runner launches cleanly
    # as root on Railway with no extra args — which is why it already works here.
    return {'headless': not headed}


@pytest.fixture(scope='session', autouse=True)
def _require_live_session():
    """Abort the whole run up front unless the dashboard still accepts the stored session.

    `_session_is_valid` can only see cookie presence + local expiry, and the dashboard revokes
    sessions server-side long before that expiry. Without this gate a dead session runs all the way
    through: every page is /login, so tests fail on sidebar nav links with `Element not found` and
    look like per-test locator bugs. Failing here instead names the real cause once.

    A liveness check that cannot reach the dashboard (offline, 5xx) is inconclusive, NOT a failure —
    those runs proceed exactly as before.
    """
    if not _session_is_valid():
        pytest.fail(
            'No usable stored session at '
            f'{SESSION_PATH} — its auth cookies are missing or expired, so every page would be the '
            'login page. Re-run `python capture_session.py <EnvName>` from backend/ to refresh it '
            '(a human must clear the email OTP).',
            pytrace=False,
        )

    try:
        import sys
        if BACKEND_ROOT not in sys.path:
            sys.path.insert(0, BACKEND_ROOT)
        from utils.session_liveness import REVOKED, UNKNOWN, check_session
    except Exception as exc:
        print(f'[conftest] session liveness check unavailable ({exc}) — proceeding unverified')
        return

    state, detail = check_session(SESSION_PATH, DASHBOARD_URL)
    if state == REVOKED:
        pytest.fail(
            f'The dashboard has revoked the stored session ({detail}). Its cookies still look '
            'unexpired, which is why nothing upstream caught it — but every page in this run would '
            'be the login page. Re-run `python capture_session.py <EnvName>` from backend/ to '
            'refresh data/.auth/session.json, and on a deployed box scp the refreshed file up. '
            'Capturing a new session invalidates the previous one, so only one machine can hold a '
            'live session at a time.',
            pytrace=False,
        )
    if state == UNKNOWN:
        print(f'[conftest] could not confirm session liveness ({detail}) — proceeding anyway')
    else:
        print(f'[conftest] {detail}')


@pytest.fixture(scope='session', autouse=True)
def _report_active_publisher(_require_live_session):
    """Report which publisher the stored session is logged into — NEVER switch it.

    The dashboard is multi-publisher and the active org is decided by the session
    (the publisher_agency cookie), not the URL. Reusing a stale .auth/session.json can
    silently run tests against the wrong publisher. We read the authoritative publisher
    from the dashboard's /api/user/ and log it, so every run is unambiguously attributed.
    Tests run against whatever publisher the session is on; to target a different one,
    log in with / supply a session for that publisher — the agent does not switch orgs.
    """
    # _require_live_session has already proven the session is usable, so no re-check here.
    try:
        import sys
        sys.path.insert(0, BACKEND_ROOT)
        from pipeline.infrastructure.publisher import PublisherDetector
        pub = PublisherDetector.detect(DASHBOARD_URL, SESSION_PATH)
    except Exception:
        pub = None
    if pub and pub.get('name'):
        print(f"[conftest] active publisher (from session): {pub['name']} ({pub.get('slug')}) "
              "— running against THIS publisher, no switching")
        expected = (os.environ.get('DASHBOARD_PUBLISHER') or '').strip()
        if expected and expected.lower() not in pub['name'].lower():
            print(f"[conftest] NOTE: session is on '{pub['name']}' but '{expected}' was expected. "
                  "Use a session/URL logged into the publisher you want — the agent will not switch.")
    else:
        print('[conftest] could not detect active publisher from /api/user/ — '
              'running with whatever the session holds')


@pytest.fixture(scope='session')
def browser_context_args(browser_context_args, _require_live_session):
    args = dict(browser_context_args)
    args['base_url'] = DASHBOARD_URL

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
