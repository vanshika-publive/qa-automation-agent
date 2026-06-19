import os
import threading

_thread_local = threading.local()


def set_runtime_credentials(creds):
    _thread_local.credentials = dict(creds)


def clear_runtime_credentials():
    if hasattr(_thread_local, 'credentials'):
        del _thread_local.credentials


def _resolve(env_key, override_key):
    if hasattr(_thread_local, 'credentials'):
        val = _thread_local.credentials.get(override_key)
        if val:
            return val
    val = os.environ.get(env_key)
    if val:
        return val
    raise RuntimeError(
        f'Missing credential: {env_key}\n'
        'Set it in .env or via set_runtime_credentials().'
    )


def _resolve_optional(env_key, override_key):
    if hasattr(_thread_local, 'credentials'):
        val = _thread_local.credentials.get(override_key)
        if val:
            return val
    return os.environ.get(env_key) or None


def get_credentials():
    return {
        'openai_api_key': _resolve('OPENAI_API_KEY', 'openai_api_key'),
        'dashboard_url': _resolve('DASHBOARD_URL', 'dashboard_url'),
        'dashboard_email': _resolve('DASHBOARD_EMAIL', 'dashboard_email'),
        'dashboard_password': _resolve('DASHBOARD_PASSWORD', 'dashboard_password'),
        'dashboard_session': _resolve_optional('DASHBOARD_SESSION', 'dashboard_session'),
    }


def get_dashboard_credentials():
    return {
        'dashboard_url': _resolve('DASHBOARD_URL', 'dashboard_url'),
        'dashboard_email': _resolve('DASHBOARD_EMAIL', 'dashboard_email'),
        'dashboard_password': _resolve('DASHBOARD_PASSWORD', 'dashboard_password'),
    }
