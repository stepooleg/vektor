"""Разбор SMTP-конфигурации deployment-среды (SPEC §10.3, issue #44)."""

from __future__ import annotations

from collections.abc import Mapping

from django.core.exceptions import ImproperlyConfigured


def _boolean(environ: Mapping[str, str], name: str, *, default: bool = False) -> bool:
    """Разобрать boolean env-переменную."""
    raw = environ.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    msg = f"{name} содержит недопустимое boolean-значение: {raw!r}"
    raise ImproperlyConfigured(msg)


def _positive_int(environ: Mapping[str, str], name: str, *, default: int) -> int:
    """Разобрать положительное целое из env-переменной."""
    try:
        value = int(environ.get(name, str(default)))
    except ValueError as error:
        raise ImproperlyConfigured(f"{name} должен быть целым числом") from error
    if value <= 0:
        raise ImproperlyConfigured(f"{name} должен быть больше нуля")
    return value


def _positive_float(environ: Mapping[str, str], name: str, *, default: float) -> float:
    """Разобрать положительное число из env-переменной."""
    try:
        value = float(environ.get(name, str(default)))
    except ValueError as error:
        raise ImproperlyConfigured(f"{name} должен быть числом") from error
    if value <= 0:
        raise ImproperlyConfigured(f"{name} должен быть больше нуля")
    return value


def build_smtp_settings(environ: Mapping[str, str]) -> dict[str, object]:
    """Сформировать настройки Django SMTP из env-переменных установки."""
    host = environ.get("EMAIL_HOST", "")
    use_tls = _boolean(environ, "EMAIL_USE_TLS", default=True)
    use_ssl = _boolean(environ, "EMAIL_USE_SSL")
    if use_tls and use_ssl:
        msg = "EMAIL_USE_TLS и EMAIL_USE_SSL нельзя включать одновременно"
        raise ImproperlyConfigured(msg)
    if host not in {"", "localhost", "127.0.0.1", "::1"} and not use_tls and not use_ssl:
        msg = "SMTP требует EMAIL_USE_TLS=True или EMAIL_USE_SSL=True"
        raise ImproperlyConfigured(msg)
    username = environ.get("EMAIL_HOST_USER", "")
    password = environ.get("EMAIL_HOST_PASSWORD", "")
    if bool(username) != bool(password):
        msg = "EMAIL_HOST_USER и EMAIL_HOST_PASSWORD задаются только вместе"
        raise ImproperlyConfigured(msg)
    return {
        "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "EMAIL_HOST": host,
        "EMAIL_PORT": _positive_int(environ, "EMAIL_PORT", default=587),
        "EMAIL_USE_TLS": use_tls,
        "EMAIL_USE_SSL": use_ssl,
        "EMAIL_HOST_USER": username,
        "EMAIL_HOST_PASSWORD": password,
        "DEFAULT_FROM_EMAIL": environ.get("DEFAULT_FROM_EMAIL", "Vektor <no-reply@vektor.local>"),
        "EMAIL_TIMEOUT": _positive_float(environ, "EMAIL_TIMEOUT", default=15),
    }
