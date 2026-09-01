"""Проверка deployment-команды SMTP (issue #44)."""

from __future__ import annotations

from io import StringIO

from django.core import mail
from django.core.management import call_command


def test_verify_smtp_sends_non_personal_test_message() -> None:
    """Команда проверяет настроенный backend без вывода адреса или credentials."""
    stdout = StringIO()

    call_command("verify_smtp", "recipient@example.test", stdout=stdout)

    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["recipient@example.test"]
    assert message.subject == "Vektor: проверка SMTP"
    assert "персональных данных" in message.body
    assert "recipient@example.test" not in stdout.getvalue()
    assert "SMTP-проверка успешно отправлена" in stdout.getvalue()
