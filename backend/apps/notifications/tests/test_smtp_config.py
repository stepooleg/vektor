"""Deployment-контракт SMTP без привязки к площадке клиента (issue #44)."""

from __future__ import annotations

import pytest
from django.core.exceptions import ImproperlyConfigured

from apps.notifications.smtp_config import build_smtp_settings


def test_authenticated_starttls_smtp_is_built_from_environment() -> None:
    """Внешний SMTP использует env-реквизиты и защищённый transport."""
    smtp = build_smtp_settings(
        {
            "EMAIL_HOST": "smtp.example.test",
            "EMAIL_PORT": "587",
            "EMAIL_USE_TLS": "True",
            "EMAIL_USE_SSL": "False",
            "EMAIL_HOST_USER": "vektor-sender",
            "EMAIL_HOST_PASSWORD": "deployment-secret",
            "DEFAULT_FROM_EMAIL": "Vektor <no-reply@example.test>",
            "EMAIL_TIMEOUT": "20",
        }
    )

    assert smtp == {
        "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "EMAIL_HOST": "smtp.example.test",
        "EMAIL_PORT": 587,
        "EMAIL_USE_TLS": True,
        "EMAIL_USE_SSL": False,
        "EMAIL_HOST_USER": "vektor-sender",
        "EMAIL_HOST_PASSWORD": "deployment-secret",
        "DEFAULT_FROM_EMAIL": "Vektor <no-reply@example.test>",
        "EMAIL_TIMEOUT": 20.0,
    }


def test_smtp_rejects_conflicting_tls_modes() -> None:
    """STARTTLS и implicit SSL нельзя включить одновременно."""
    with pytest.raises(ImproperlyConfigured, match="EMAIL_USE_TLS"):
        build_smtp_settings(
            {
                "EMAIL_HOST": "smtp.example.test",
                "EMAIL_USE_TLS": "True",
                "EMAIL_USE_SSL": "True",
            }
        )


def test_smtp_requires_encrypted_transport() -> None:
    """Учётные и персональные данные нельзя отправлять через plaintext SMTP."""
    with pytest.raises(ImproperlyConfigured, match="TLS"):
        build_smtp_settings(
            {
                "EMAIL_HOST": "smtp.example.test",
                "EMAIL_USE_TLS": "False",
                "EMAIL_USE_SSL": "False",
            }
        )


def test_local_smtp_catcher_may_use_plaintext() -> None:
    """Mailpit/MailHog на loopback остаётся доступен для локальной разработки."""
    smtp = build_smtp_settings(
        {
            "EMAIL_HOST": "localhost",
            "EMAIL_PORT": "1025",
            "EMAIL_USE_TLS": "False",
            "EMAIL_USE_SSL": "False",
        }
    )

    assert smtp["EMAIL_HOST"] == "localhost"
    assert smtp["EMAIL_USE_TLS"] is False


def test_smtp_rejects_partial_credentials() -> None:
    """Логин и пароль задаются вместе либо оба пусты для trusted relay."""
    with pytest.raises(ImproperlyConfigured, match="EMAIL_HOST_USER"):
        build_smtp_settings(
            {
                "EMAIL_USE_TLS": "True",
                "EMAIL_HOST_USER": "vektor-sender",
            }
        )


def test_smtp_rejects_unknown_boolean_value() -> None:
    """Опечатка в флаге защиты не должна молча менять режим подключения."""
    with pytest.raises(ImproperlyConfigured, match="perhaps"):
        build_smtp_settings({"EMAIL_USE_TLS": "perhaps"})


@pytest.mark.parametrize(
    ("name", "value"),
    [("EMAIL_PORT", "not-a-port"), ("EMAIL_TIMEOUT", "0")],
)
def test_smtp_rejects_invalid_numeric_settings(name: str, value: str) -> None:
    """Некорректные числовые параметры выявляются при старте приложения."""
    with pytest.raises(ImproperlyConfigured, match=name):
        build_smtp_settings({"EMAIL_USE_TLS": "True", name: value})


def test_implicit_ssl_relay_without_credentials_is_supported() -> None:
    """Внутренний trusted relay может работать без SMTP-аутентификации."""
    smtp = build_smtp_settings(
        {
            "EMAIL_HOST": "relay.example.test",
            "EMAIL_PORT": "465",
            "EMAIL_USE_TLS": "False",
            "EMAIL_USE_SSL": "True",
        }
    )

    assert smtp["EMAIL_USE_SSL"] is True
    assert smtp["EMAIL_HOST_USER"] == ""
    assert smtp["EMAIL_HOST_PASSWORD"] == ""
