"""Настройки для автотестов (pytest-django).

Принципы:
- быстрые и изолированные: SQLite in-memory (unit-тесты не требуют PostgreSQL);
- детерминированные: MD5-хешер паролей для скорости;
- безопасность: отладка выключена.

Наследуется от ``base`` и переопределяет только БД/хешер/логирование.
При желании в CI гонять на PostgreSQL — переопределить ``DATABASE_URL``
(см. ``.github/workflows/ci.yml``).
"""

from __future__ import annotations

from .base import *

# ---------------------------------------------------------------------------
# База данных — быстрая in-memory SQLite для unit-тестов каркаса.
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}

# Скорость тестов: дорогие хешеры не нужны.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

DEBUG = False
TEMPLATE_DEBUG = False

# Без email/push в тестах.
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Celery-задачи в тестах выполняются синхронно (eager), если позже подключим.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Убираем валидаторы паролей, чтобы тесты с простыми паролями не падали.
AUTH_PASSWORD_VALIDATORS = []

# Подавляем шум логов в тестах.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"null": {"class": "logging.NullHandler"}},
    "root": {"handlers": ["null"], "level": "WARNING"},
}
