import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


class PublisherDetector:

    AUTH_COOKIE_NAMES = ('session', 'publisher_agency')

    @staticmethod
    def detect(base_url: str, session_path: str) -> dict:
        """Return {'name','slug','id','domain'} for the publisher the stored session is
        logged into, or None if it cannot be determined. Never mutates anything."""
        try:
            stored = json.loads(Path(session_path).read_text(encoding='utf-8'))
        except Exception:
            return None

        cookies = stored.get('cookies', [])
        if not any(c.get('name') in PublisherDetector.AUTH_COOKIE_NAMES for c in cookies):
            return None

        host = urlsplit(base_url).netloc
        cookie_header = '; '.join(
            f"{c['name']}={c['value']}"
            for c in cookies
            if c.get('name') and c.get('value')
            and c.get('domain', '').lstrip('.') in host
        )

        req = Request(
            f'{PublisherDetector._origin(base_url)}/api/user/',
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

    @staticmethod
    def _origin(base_url: str) -> str:
        parts = urlsplit(base_url)
        return f'{parts.scheme}://{parts.netloc}'
