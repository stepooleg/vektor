"""Проверка доставки через SMTP, настроенный на площадке клиента."""

from __future__ import annotations

from typing import Any

from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError, CommandParser


class Command(BaseCommand):
    """Отправить безопасное техническое письмо через текущий mail backend."""

    help = "Отправляет тестовое письмо для проверки deployment-конфигурации SMTP."

    def add_arguments(self, parser: CommandParser) -> None:
        """Принять адрес технического получателя без credentials."""
        parser.add_argument("recipient", help="Адрес получателя тестового письма")

    def handle(self, *args: Any, **options: Any) -> None:
        """Проверить доставку, не выводя адрес и параметры подключения."""
        try:
            sent = send_mail(
                subject="Vektor: проверка SMTP",
                message=(
                    "Техническое тестовое письмо Vektor. "
                    "Сообщение не содержит персональных данных."
                ),
                from_email=None,
                recipient_list=[options["recipient"]],
                fail_silently=False,
            )
        except Exception as error:
            msg = "SMTP-проверка не пройдена; проверьте endpoint, TLS/CA и credentials."
            raise CommandError(msg) from error

        if sent != 1:
            raise CommandError("SMTP backend не подтвердил отправку тестового письма.")
        self.stdout.write(self.style.SUCCESS("SMTP-проверка успешно отправлена."))
