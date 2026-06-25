import os
import threading


class CredentialManager:

    _thread_local = threading.local()

    @classmethod
    def set(cls, creds: dict) -> None:
        cls._thread_local.credentials = dict(creds)

    @classmethod
    def clear(cls) -> None:
        if hasattr(cls._thread_local, 'credentials'):
            del cls._thread_local.credentials

    @classmethod
    def get_all(cls) -> dict:
        return {
            'openai_api_key': cls._resolve('OPENAI_API_KEY', 'openai_api_key'),
            'dashboard_url': cls._resolve('DASHBOARD_URL', 'dashboard_url'),
            'dashboard_email': cls._resolve('DASHBOARD_EMAIL', 'dashboard_email'),
            'dashboard_password': cls._resolve('DASHBOARD_PASSWORD', 'dashboard_password'),
            'dashboard_session': cls._resolve_optional('DASHBOARD_SESSION', 'dashboard_session'),
            'dashboard_publisher': cls._resolve_optional('DASHBOARD_PUBLISHER', 'dashboard_publisher'),
        }

    @classmethod
    def get_dashboard(cls) -> dict:
        return {
            'dashboard_url': cls._resolve('DASHBOARD_URL', 'dashboard_url'),
            'dashboard_email': cls._resolve('DASHBOARD_EMAIL', 'dashboard_email'),
            'dashboard_password': cls._resolve('DASHBOARD_PASSWORD', 'dashboard_password'),
            'dashboard_publisher': cls._resolve_optional('DASHBOARD_PUBLISHER', 'dashboard_publisher'),
        }

    @classmethod
    def get_publisher(cls) -> str:
        return cls._resolve_optional('DASHBOARD_PUBLISHER', 'dashboard_publisher') or ''

    @classmethod
    def _resolve(cls, env_key: str, override_key: str) -> str:
        if hasattr(cls._thread_local, 'credentials'):
            val = cls._thread_local.credentials.get(override_key)
            if val:
                return val
        val = os.environ.get(env_key)
        if val:
            return val
        raise RuntimeError(
            f'Missing credential: {env_key}\n'
            'Set it in .env or via CredentialManager.set().'
        )

    @classmethod
    def _resolve_optional(cls, env_key: str, override_key: str):
        if hasattr(cls._thread_local, 'credentials'):
            val = cls._thread_local.credentials.get(override_key)
            if val:
                return val
        return os.environ.get(env_key) or None
