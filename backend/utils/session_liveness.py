import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

# Real (server-side) liveness check for the stored MFA session.
#
# The dashboard revokes sessions server-side well before the cookie's own `expires` — capturing a
# new session elsewhere invalidates the older one. A structural check ("the auth cookies are present
# and unexpired") therefore reports a dead session as usable: on 2026-07-29 the EC2 box's cookies
# claimed 6 more hours of validity while /api/user/ already returned 401, so all four pipeline stages
# ran logged out and failed with misleading `Element not found` errors on sidebar nav links.
# Only the dashboard can say whether a cookie is still accepted, so ask it.
#
# Stdlib-only and free of Django imports on purpose: this module is imported by the pytest harness
# (harness/conftest.py), which runs in a subprocess where DJANGO_SETTINGS_MODULE is not configured —
# anything reaching core.models raises ImproperlyConfigured there.

# The session is accepted by the dashboard.
LIVE = 'live'
# The dashboard actively rejected the cookies — re-capture is the only fix.
REVOKED = 'revoked'
# Could not determine (network down, 5xx, unreadable file). Callers must NOT treat this as dead.
UNKNOWN = 'unknown'

# Only these cookies carry the dashboard login (see conftest for why __cf_bm/analytics don't count).
AUTH_COOKIE_NAMES = ('session', 'publisher_agency')

USER_ENDPOINT = '/api/user/'
DEFAULT_TIMEOUT_SECONDS = 10


def check_session(session_path: str, base_url: str, timeout: int = DEFAULT_TIMEOUT_SECONDS):
    """Ask the dashboard whether the stored session is still accepted.

    Returns ``(state, detail)`` where state is LIVE / REVOKED / UNKNOWN and detail is a
    human-readable one-liner safe to print (never contains cookie values).
    """
    try:
        stored = json.loads(Path(session_path).read_text(encoding='utf-8'))
    except Exception as exc:
        return UNKNOWN, f'could not read {session_path}: {exc}'

    cookies = stored.get('cookies') or []
    if not any(c.get('name') in AUTH_COOKIE_NAMES for c in cookies):
        return REVOKED, (
            f'stored session carries no {"/".join(AUTH_COOKIE_NAMES)} cookie — it is not a login'
        )

    parts = urlsplit(base_url)
    origin = f'{parts.scheme}://{parts.netloc}'
    endpoint = f'{origin}{USER_ENDPOINT}'
    request = Request(
        endpoint,
        headers={
            'Cookie': _cookie_header(cookies, parts.netloc),
            'Accept': 'application/json',
        },
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            content_type = (response.headers.get('content-type') or '').lower()
            body = response.read().decode('utf-8', 'replace')
    except HTTPError as exc:
        if exc.code in (401, 403):
            return REVOKED, f'{endpoint} returned {exc.code} — the dashboard has invalidated it'
        return UNKNOWN, f'{endpoint} returned HTTP {exc.code}'
    except Exception as exc:
        # DNS failure, connection refused, timeout — the session may well be fine.
        return UNKNOWN, f'could not reach {endpoint}: {type(exc).__name__}: {exc}'

    # A logged-out request is redirected to the SPA, which urlopen follows and returns as 200 HTML.
    if 'json' not in content_type:
        return REVOKED, f'{endpoint} served HTML, not JSON — the request was redirected to /login'

    try:
        data = json.loads(body)
    except ValueError:
        return UNKNOWN, f'{endpoint} returned a non-JSON body'

    publisher = (data.get('publisher') or {}).get('name')
    if not publisher and not (data.get('user') or {}).get('email'):
        return REVOKED, f'{endpoint} carried no authenticated user'
    return LIVE, f'session is live (publisher: {publisher or "unknown"})'


def _cookie_header(cookies, host: str) -> str:
    """Serialize the stored cookies that belong to ``host``. Mirrors PublisherDetector's filter."""
    return '; '.join(
        f"{c['name']}={c['value']}"
        for c in cookies
        if c.get('name') and c.get('value')
        and c.get('domain', '').lstrip('.') in host
    )
