"""Настройки локальной разработки.

От base отличаются: DEBUG включён, белые списки хостов расширены,
подключается django-extensions-подобный вывод SQL по флагу, уровень логирования
поднимается до INFO/DEBUG.
"""

from __future__ import annotations

import os

from .base import *  # стандартный паттерн Django-settings

# DEBUG из env, по умолчанию True для dev.
DEBUG = True

# Локальная разработка: по умолчанию SQLite, чтобы manage.py-команды работали
# без Docker/PostgreSQL. В Docker .env задаёт DATABASE_URL → PostgreSQL 16.
# (Это не влияет на CI/тесты — там test.py со своим in-memory SQLite.)
if not os.environ.get("DATABASE_URL"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# В dev расширяем допустимые хосты явно (прод-список см. в base.py).
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

# В dev расслабляем cookie-настройки (фронт на Vite — :5173).
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]

# ---------------------------------------------------------------------------
# Логирование — шумный вывод SQL по флагу Vektor_SQL_LOG=1
# ---------------------------------------------------------------------------
_LOG_SQL = os.environ.get("VEKTOR_SQL_LOG", "0") == "1"
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "dev": {"format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "dev"},
    },
    "root": {"handlers": ["console"], "level": "DEBUG" if _LOG_SQL else "INFO"},
    "loggers": {
        "django.db.backends": {"level": "DEBUG" if _LOG_SQL else "INFO"},
        "vektor": {"level": "DEBUG"},
    },
}
