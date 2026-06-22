"""Detect the publisher a stored dashboard session is logged into.

The dashboard is multi-publisher; the active publisher is determined by the session
(the `publisher_agency` cookie), NOT by the URL path. To avoid stale-session confusion
— silently running tests against the wrong publisher — we read the dashboard's own
`GET /api/user/` endpoint, which returns the authoritative publisher for the session.

This module is read-only on purpose: it NEVER switches publisher. Switching publisher is
the user's responsibility (log in / supply a session for that publisher); the agent always
runs against whichever publisher the session is currently on, and reports which one that is.
"""
import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

# Cookies that actually carry the dashboard login (match conftest / login_helper).
AUTH_COOKIE_NAMES = ('session', 'publisher_agency')


def _origin(base_url):
    parts = urlsplit(base_url)
    return f'{parts.scheme}://{parts.netloc}'


def detect_active_publisher(base_url, session_path):
    """Return {'name','slug','id','domain'} for the publisher the stored session is
    logged into, or None if it can't be determined (no/invalid session, network error).
    Never mutates anything."""
    try:
        stored = json.loads(Path(session_path).read_text(encoding='utf-8'))
    except Exception:
        return None

    cookies = stored.get('cookies', [])
    if not any(c.get('name') in AUTH_COOKIE_NAMES for c in cookies):
        return None

    host = urlsplit(base_url).netloc
    cookie_header = '; '.join(
        f"{c['name']}={c['value']}"
        for c in cookies
        if c.get('name') and c.get('value')
        and c.get('domain', '').lstrip('.') in host
    )

    req = Request(
        f'{_origin(base_url)}/api/user/',
        headers={'Cookie': cookie_header, 'Accept': 'application/json'},
    )
    try:
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except Exception:
        return None

    pub = data.get('publisher') or {}
    if not pub.get('name'):
        return None
    return {
        'name': pub.get('name') or '',
        'slug': pub.get('slug') or '',
        'id': pub.get('id'),
        'domain': pub.get('actual_domain') or '',
    }
