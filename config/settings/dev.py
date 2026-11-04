# config/settings/dev.py

from .base import *

# -----------------------------------------------------------------------------
# Настройки для разработки (локально)
# -----------------------------------------------------------------------------

# Отключаем ManifestStaticFilesStorage для разработки (удобнее работать со статикой)
STORAGES["staticfiles"]["BACKEND"] = "django.contrib.staticfiles.storage.StaticFilesStorage"

# Кэширование для локальной разработки.
# LocMemCache не использует файловую систему, поэтому на Windows
# не возникает PermissionError при удалении просроченных cache-файлов.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "auto-catalog-dev",
    }
}

# Разрешённые хосты
ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
]

# URL сайта для разработки
SITE_URL = 'http://127.0.0.1:8000'

# Доверенные источники для CSRF
CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]

# Отправка писем в консоль (для отладки)
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Попытка импортировать локальные настройки (для секретных ключей)
try:
    from .local import *
except ImportError:
    pass

DEBUG = True