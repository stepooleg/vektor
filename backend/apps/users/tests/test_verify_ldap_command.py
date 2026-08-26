"""Контракт deployment-проверки LDAP без хранения клиентских credentials."""

from __future__ import annotations

from io import StringIO
from types import SimpleNamespace

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings


@override_settings(AUTH_LDAP_ENABLED=False)
def test_verify_ldap_requires_enabled_client_configuration() -> None:
    """До выбора клиента команда объясняет, что LDAP намеренно отключён."""
    with pytest.raises(CommandError, match="AUTH_LDAP_ENABLED"):
        call_command("verify_ldap", "a.ivanova")


@override_settings(AUTH_LDAP_ENABLED=True)
def test_verify_ldap_uses_only_ldap_backend_and_hides_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Smoke test не использует local fallback и не печатает учётные данные."""
    identifier = "sensitive.account"
    password = "Sensitive-Pwd-12345"
    calls: list[tuple[str, str]] = []

    class FakeLdapBackend:
        def authenticate(
            self,
            request: object,
            username: str,
            password: str,
        ) -> object:
            calls.append((username, password))
            return SimpleNamespace(is_active=True)

    command_module = __import__(
        "apps.users.management.commands.verify_ldap",
        fromlist=["verify_ldap"],
    )
    monkeypatch.setattr(command_module, "getpass", lambda _prompt: password)
    monkeypatch.setattr(command_module, "load_backend", lambda _path: FakeLdapBackend())
    stdout = StringIO()

    call_command("verify_ldap", identifier, stdout=stdout)

    output = stdout.getvalue()
    assert calls == [(identifier, password)]
    assert "успеш" in output.lower()
    assert identifier not in output
    assert password not in output


@override_settings(AUTH_LDAP_ENABLED=True)
def test_verify_ldap_returns_error_for_failed_bind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Неуспешный bind даёт ненулевой exit code без раскрытия причины/логина."""
    command_module = __import__(
        "apps.users.management.commands.verify_ldap",
        fromlist=["verify_ldap"],
    )
    monkeypatch.setattr(command_module, "getpass", lambda _prompt: "wrong-password")
    monkeypatch.setattr(
        command_module,
        "load_backend",
        lambda _path: SimpleNamespace(authenticate=lambda **_kwargs: None),
    )

    with pytest.raises(CommandError, match="не пройдена") as error:
        call_command("verify_ldap", "sensitive.account")

    assert "sensitive.account" not in str(error.value)
    assert "wrong-password" not in str(error.value)
