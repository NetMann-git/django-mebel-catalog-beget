# config/settings/prod.py

from .base import *

DEBUG = False

# Production is served over HTTPS; keep local HTTP development unchanged.
SESSION_COOKIE_SECURE = config("SESSION_COOKIE_SECURE", default=True, cast=bool)
CSRF_COOKIE_SECURE = config("CSRF_COOKIE_SECURE", default=True, cast=bool)


def _env_list(name):
    """Читает список значений из .env, разделённых запятыми."""
    return [
        value.strip()
        for value in config(name).split(',')
        if value.strip()
    ]


# -----------------------------------------------------------------------------
# Домены и URL production
# -----------------------------------------------------------------------------

ALLOWED_HOSTS = _env_list('ALLOWED_HOSTS')
SITE_URL = config('SITE_URL').rstrip('/')
CSRF_TRUSTED_ORIGINS = _env_list('CSRF_TRUSTED_ORIGINS')

# -----------------------------------------------------------------------------
# База данных MySQL
# Все параметры подключения хранятся в .env и не попадают в Git.
# -----------------------------------------------------------------------------

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='3306'),
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}
