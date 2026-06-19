import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-dev-key-change-in-production')
DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 'yes')
ALLOWED_HOSTS = ['*']

PLAYWRIGHT_PROJECT_ROOT = os.getenv(
    'PLAYWRIGHT_PROJECT_ROOT',
    str(BASE_DIR),
)

INSTALLED_APPS = [
    'corsheaders',
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'rest_framework',
    'core',
    'pipeline',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
]

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'

# Database — parse DATABASE_URL or fall back to individual env vars
_database_url = os.getenv('DATABASE_URL', '')
if _database_url:
    import re
    _m = re.match(
        r'postgres(?:ql)?://(?P<user>[^:@]+)(?::(?P<password>[^@]*))?@(?P<host>[^:/]+)(?::(?P<port>\d+))?/(?P<name>[^?]+)',
        _database_url,
    )
    if _m:
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': _m.group('name'),
                'USER': _m.group('user'),
                'PASSWORD': _m.group('password') or '',
                'HOST': _m.group('host'),
                'PORT': _m.group('port') or '5432',
            }
        }
        if os.getenv('DATABASE_SSL', 'false').lower() == 'true':
            DATABASES['default']['OPTIONS'] = {'sslmode': 'require'}
    else:
        raise ValueError(f'Cannot parse DATABASE_URL: {_database_url}')
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME', 'publive_tester'),
            'USER': os.getenv('DB_USER', ''),
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '5432'),
        }
    }

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'core.renderers.EnvelopeRenderer',
    ],
    'EXCEPTION_HANDLER': 'core.exceptions.envelope_exception_handler',
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'UNAUTHENTICATED_USER': None,
}

CORS_ALLOWED_ORIGINS = [
    os.getenv('FRONTEND_URL', 'http://localhost:5173'),
]
CORS_ALLOW_ALL_ORIGINS = DEBUG

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = False
USE_TZ = False

STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
            ],
        },
    },
]
