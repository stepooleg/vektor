"""Базовые настройки Vektor (общие для всех окружений).

Спецификация продукта: ``SPEC.md``; стек зафиксирован в ``SPEC.md`` §11.1 и
ADR-0002. Секреты — только через переменные окружения (``.env`` в .gitignore).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, cast

import dj_database_url
from celery.schedules import crontab
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

from apps.notifications.smtp_config import build_smtp_settings
from apps.users.ldap_config import parse_group_role_map, validate_secure_transport

if TYPE_CHECKING:
    from typing import Any

# ---------------------------------------------------------------------------
# Пути и окружение
# ---------------------------------------------------------------------------
# backend/ — корень проекта Django; manage.py лежит рядом.
BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent

# .env подгружается, если есть (dev/local). CI передаёт переменные напрямую.
load_dotenv(BASE_DIR.parent / ".env")


def _env_bool(name: str, default: bool = False) -> bool:
    """Бережно разбирает булево из переменной окружения."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------------------
# Ядро Django
# ---------------------------------------------------------------------------
SECRET_KEY: str = os.environ.get(
    "SECRET_KEY",
    # fallback нужен, чтобы manage.py-команды работали до заполнения .env.
    # В проде SECRET_KEY обязателен и должен быть уникальным.
    "django-insecure-DEV-ONLY-CHANGE-ME",
)

DEBUG: bool = _env_bool("DEBUG", default=False)

ALLOWED_HOSTS: list[str] = [
    h.strip()
    for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if h.strip()
]

# ---------------------------------------------------------------------------
# Приложения (домены из AGENTS.md §5)
# ---------------------------------------------------------------------------
# Встроенные.
DJANGO_APPS: tuple[str, ...] = (
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
)

# Сторонние.
THIRD_PARTY_APPS: tuple[str, ...] = (
    "rest_framework",
    "drf_spectacular",
    "django_filters",
    "corsheaders",
)

# Доменные приложения Vektor (порядок — от фундамента к производным доменам).
LOCAL_APPS: tuple[str, ...] = (
    "apps.users",
    "apps.orgstructure",
    "apps.competencies",
    "apps.assessment",
    "apps.feedback",
    "apps.portfolio",
    "apps.lms",
    "apps.idp",
    "apps.analytics",
    "apps.notifications",
    "apps.audit",
)

INSTALLED_APPS: tuple[str, ...] = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
MIDDLEWARE: tuple[str, ...] = (
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
)

ROOT_URLCONF: str = "vektor.urls"

TEMPLATES: list[dict[str, Any]] = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION: str = "vektor.wsgi.application"
ASGI_APPLICATION: str = "vektor.asgi.application"

# ---------------------------------------------------------------------------
# База данных (PostgreSQL 16 в проде/dev; переопределяется в test.py)
# ---------------------------------------------------------------------------
# DATABASE_URL имеет приоритет; иначе — отдельные POSTGRES_* переменные.
_default_db_url = (
    f"postgres://{os.environ.get('POSTGRES_USER', 'vektor')}:"
    f"{os.environ.get('POSTGRES_PASSWORD', 'vektor')}@"
    f"{os.environ.get('POSTGRES_HOST', 'localhost')}:"
    f"{os.environ.get('POSTGRES_PORT', '5432')}/"
    f"{os.environ.get('POSTGRES_DB', 'vektor')}"
)
DATABASE_URL = os.environ.get("DATABASE_URL", _default_db_url)

DATABASES: dict[str, Any] = {
    "default": dj_database_url.parse(DATABASE_URL, conn_max_age=60, conn_health_checks=True),
}

# Опции подключения (PostgreSQL): режим SSL из env (SPEC §12.2 — TLS in transit).
if DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql":
    DATABASES["default"].setdefault("OPTIONS", {})
    # Безопасно добавляем sslmode только для Postgres-коннектора.
    sslmode = os.environ.get("DB_SSLMODE", "prefer")
    DATABASES["default"]["OPTIONS"] = {"sslmode": sslmode}

# ---------------------------------------------------------------------------
# Аутентификация (SPEC §10.2, §12.2)
# ---------------------------------------------------------------------------
# Argon2 — основной алгоритм хеширования паролей (SPEC §12.2).
PASSWORD_HASHERS: list[str] = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS: list[dict[str, Any]] = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL: str = "/auth/login/"
LOGIN_REDIRECT_URL: str = "/"

# Кастомная модель пользователя (SPEC §10.2, §2). Домен apps.users.
AUTH_USER_MODEL: str = "users.User"

# Прямой LDAP bind к Active Directory (ADR 0006, SPEC §10.2, issue #42).
AUTH_LDAP_ENABLED: bool = _env_bool("AUTH_LDAP_ENABLED", default=False)
AUTH_LDAP_SERVER_URI: str = os.environ.get("AUTH_LDAP_SERVER_URI", "")
AUTH_LDAP_BIND_DN: str = os.environ.get("AUTH_LDAP_BIND_DN", "")
AUTH_LDAP_BIND_PASSWORD: str = os.environ.get("AUTH_LDAP_BIND_PASSWORD", "")
AUTH_LDAP_USER_SEARCH_BASE: str = os.environ.get("AUTH_LDAP_USER_SEARCH_BASE", "")
AUTH_LDAP_START_TLS: bool = _env_bool("AUTH_LDAP_START_TLS", default=False)
AUTH_LDAP_ALLOW_INSECURE: bool = _env_bool("AUTH_LDAP_ALLOW_INSECURE", default=False)
AUTH_LDAP_CA_CERT_FILE: str = os.environ.get("AUTH_LDAP_CA_CERT_FILE", "")
AUTH_LDAP_ALWAYS_UPDATE_USER: bool = True
AUTH_LDAP_USER_QUERY_FIELD: str = "email"
AUTH_LDAP_USER_ATTR_MAP: dict[str, str] = {
    "email": "mail",
    "first_name": "displayName",
}
# django-auth-ldap декодирует LDAPSearch как UTF-8; бинарное фото читается
# отдельным base-object search в VektorLDAPBackend.
AUTH_LDAP_USER_ATTRLIST: list[str] = ["mail", "displayName", "memberOf"]
AUTH_LDAP_GROUP_ROLE_MAP: dict[str, str] = parse_group_role_map(
    os.environ.get("AUTH_LDAP_GROUP_ROLE_MAP", "")
)

if AUTH_LDAP_ENABLED:
    if not AUTH_LDAP_SERVER_URI or not AUTH_LDAP_USER_SEARCH_BASE:
        from django.core.exceptions import ImproperlyConfigured

        msg = "Для LDAP обязательны AUTH_LDAP_SERVER_URI и AUTH_LDAP_USER_SEARCH_BASE."
        raise ImproperlyConfigured(msg)

    validate_secure_transport(
        AUTH_LDAP_SERVER_URI,
        start_tls=AUTH_LDAP_START_TLS,
        allow_insecure=AUTH_LDAP_ALLOW_INSECURE,
    )

    import ldap
    from django_auth_ldap.config import LDAPSearch

    AUTH_LDAP_CONNECTION_OPTIONS: dict[int, object] = {
        ldap.OPT_X_TLS_REQUIRE_CERT: ldap.OPT_X_TLS_DEMAND,
    }
    if AUTH_LDAP_CA_CERT_FILE:
        AUTH_LDAP_CONNECTION_OPTIONS[ldap.OPT_X_TLS_CACERTFILE] = AUTH_LDAP_CA_CERT_FILE

    AUTH_LDAP_USER_SEARCH = LDAPSearch(
        AUTH_LDAP_USER_SEARCH_BASE,
        ldap.SCOPE_SUBTREE,
        "(|(sAMAccountName=%(user)s)(userPrincipalName=%(user)s))",
        attrlist=AUTH_LDAP_USER_ATTRLIST,
    )

LOCAL_LOGIN_ENABLED: bool = _env_bool("LOCAL_LOGIN_ENABLED", default=True)

# LDAP проверяется первым; local fallback требует глобального и пользовательского флагов.
AUTHENTICATION_BACKENDS: tuple[str, ...] = (
    *(("apps.users.ldap_backend.VektorLDAPBackend",) if AUTH_LDAP_ENABLED else ()),
    *(("apps.users.local_backend.LocalModelBackend",) if LOCAL_LOGIN_ENABLED else ()),
)

# Защита от перебора паролей (SPEC §10.2): lockout после N неудачных попыток.
LOGIN_MAX_ATTEMPTS: int = int(os.environ.get("LOGIN_MAX_ATTEMPTS", "5"))
# Окно lockout в секундах (после истечения — новая попытка разрешена).
LOGIN_LOCKOUT_SECONDS: int = int(os.environ.get("LOGIN_LOCKOUT_SECONDS", "900"))

# Кеш для счётчиков неудачных входов (fallback на local-memory, prod — Redis).
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "vektor-default",
    }
}

# ---------------------------------------------------------------------------
# Email (SMTP, SPEC §10.3) — только deployment-конфигурация
# ---------------------------------------------------------------------------
_smtp = build_smtp_settings(os.environ)
EMAIL_BACKEND: str = cast(str, _smtp["EMAIL_BACKEND"])
EMAIL_HOST: str = cast(str, _smtp["EMAIL_HOST"])
EMAIL_PORT: int = cast(int, _smtp["EMAIL_PORT"])
EMAIL_USE_TLS: bool = cast(bool, _smtp["EMAIL_USE_TLS"])
EMAIL_USE_SSL: bool = cast(bool, _smtp["EMAIL_USE_SSL"])
EMAIL_HOST_USER: str = cast(str, _smtp["EMAIL_HOST_USER"])
EMAIL_HOST_PASSWORD: str = cast(str, _smtp["EMAIL_HOST_PASSWORD"])
DEFAULT_FROM_EMAIL: str = cast(str, _smtp["DEFAULT_FROM_EMAIL"])
EMAIL_TIMEOUT: float = cast(float, _smtp["EMAIL_TIMEOUT"])

# ---------------------------------------------------------------------------
# Web Push (PWA, SPEC §10.4) — VAPID-ключи
# ---------------------------------------------------------------------------
# TODO(#24): VAPID-ключи должны генерироваться и храниться в секрете (env).
VAPID_PUBLIC_KEY: str = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY: str = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_SUBJECT: str = os.environ.get("VAPID_SUBJECT", "mailto:no-reply@example.local")

# ---------------------------------------------------------------------------
# Internationalisation — только русский (SPEC §15)
# ---------------------------------------------------------------------------
LANGUAGE_CODE: str = "ru-ru"
TIME_ZONE: str = "Europe/Moscow"
USE_I18N: bool = True
USE_TZ: bool = True

# ---------------------------------------------------------------------------
# Статика и медиа
# ---------------------------------------------------------------------------
STATIC_URL: str = "/static/"
STATIC_ROOT: Path = BASE_DIR / "staticfiles"
MEDIA_URL: str = "/media/"
MEDIA_ROOT: Path = BASE_DIR / "media"

# ---------------------------------------------------------------------------
# Безопасность (SPEC §12.2) — прод-настройки; в dev/test ослабляются
# ---------------------------------------------------------------------------
SECURE_BROWSER_XSS_FILTER: bool = True
X_FRAME_OPTIONS: str = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF: bool = True
SECURE_REFERRER_POLICY: str = "same-origin"
SESSION_COOKIE_HTTPONLY: bool = True
CSRF_COOKIE_HTTPONLY: bool = True

DEFAULT_AUTO_FIELD: str = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# DRF + drf-spectacular
# ---------------------------------------------------------------------------
REST_FRAMEWORK: dict[str, Any] = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework.authentication.SessionAuthentication",),
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.NamespaceVersioning",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

SPECTACULAR_SETTINGS: dict[str, Any] = {
    "TITLE": "Vektor API",
    "DESCRIPTION": "Корпоративное HR-приложение: оценка 360°, LMS, ИПР, портфолио.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

# ---------------------------------------------------------------------------
# CORS (on-premise: фронт и бэк обычно на одном хосте через Nginx)
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS: list[str] = [
    o.strip()
    for o in os.environ.get(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if o.strip()
]

# ---------------------------------------------------------------------------
# Celery + Redis (очереди/фон, SPEC §11.1)
# ---------------------------------------------------------------------------
CELERY_BROKER_URL: str = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/1")
CELERY_RESULT_BACKEND: str = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
CELERY_ACCEPT_CONTENT: list[str] = ["json"]
CELERY_TASK_SERIALIZER: str = "json"
CELERY_RESULT_SERIALIZER: str = "json"
CELERY_TIMEZONE: str = TIME_ZONE

# ---------------------------------------------------------------------------
# Интеграция с 1С:ЗУП (SPEC §10.1, issue #41)
# ---------------------------------------------------------------------------
ONEC_SYNC_ENABLED: bool = _env_bool("ONEC_SYNC_ENABLED")
ONEC_BASE_URL: str = os.environ.get("ONEC_BASE_URL", "")
ONEC_AUTH_MODE: str = os.environ.get("ONEC_AUTH_MODE", "basic").lower()
ONEC_USERNAME: str = os.environ.get("ONEC_USERNAME", "")
ONEC_PASSWORD: str = os.environ.get("ONEC_PASSWORD", "")
ONEC_OAUTH_TOKEN: str = os.environ.get("ONEC_OAUTH_TOKEN", "")
ONEC_TIMEOUT_SECONDS: float = float(os.environ.get("ONEC_TIMEOUT_SECONDS", "15"))
ONEC_SYNC_CRON: str = os.environ.get("ONEC_SYNC_CRON", "0 2 * * *")
_onec_cron_parts = ONEC_SYNC_CRON.split()
if len(_onec_cron_parts) != 5:
    raise ImproperlyConfigured("ONEC_SYNC_CRON должен содержать пять полей cron")

CELERY_BEAT_SCHEDULE: dict[str, dict[str, object]] = {
    "assessment-retention-daily": {
        "task": "assessment.retention_daily",
        "schedule": crontab(hour=3, minute=0),
    },
}
if ONEC_SYNC_ENABLED:
    _minute, _hour, _day_of_month, _month_of_year, _day_of_week = _onec_cron_parts
    CELERY_BEAT_SCHEDULE["orgstructure-onec-sync"] = {
        "task": "orgstructure.sync_nightly",
        "schedule": crontab(
            minute=_minute,
            hour=_hour,
            day_of_month=_day_of_month,
            month_of_year=_month_of_year,
            day_of_week=_day_of_week,
        ),
    }

# ---------------------------------------------------------------------------
# Комплаенс (SPEC §12.6, issue #43)
# ---------------------------------------------------------------------------
# Каноническая настройка — годы. DATA_RETENTION_MONTHS временно поддерживается
# для совместимости с окружениями, созданными до решения по issue #43.
_retention_years = os.environ.get("DATA_RETENTION_YEARS")
if _retention_years is None:
    _retention_months = int(os.environ.get("DATA_RETENTION_MONTHS", "60"))
    if _retention_months <= 0 or _retention_months % 12 != 0:
        raise ImproperlyConfigured("DATA_RETENTION_MONTHS должен задавать целое число лет")
    DATA_RETENTION_YEARS: int = _retention_months // 12
else:
    DATA_RETENTION_YEARS = int(_retention_years)
    if DATA_RETENTION_YEARS <= 0:
        raise ImproperlyConfigured("DATA_RETENTION_YEARS должен быть положительным")

ASSESSMENT_AGGREGATE_RETENTION_MODE: str = os.environ.get(
    "ASSESSMENT_AGGREGATE_RETENTION_MODE", "archive"
).lower()
if ASSESSMENT_AGGREGATE_RETENTION_MODE not in {"archive", "delete"}:
    raise ImproperlyConfigured("ASSESSMENT_AGGREGATE_RETENTION_MODE должен быть archive или delete")

AUDIT_LOG_RETENTION_MONTHS: int = int(os.environ.get("AUDIT_LOG_RETENTION_MONTHS", "72"))
