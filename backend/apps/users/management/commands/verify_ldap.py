"""Безопасная deployment-проверка LDAP bind и синхронизации профиля."""

from __future__ import annotations

from getpass import getpass
from typing import Any

from django.conf import settings
from django.contrib.auth import load_backend
from django.core.management.base import BaseCommand, CommandError, CommandParser

LDAP_BACKEND = "apps.users.ldap_backend.VektorLDAPBackend"


class Command(BaseCommand):
    """Проверить клиентскую LDAP-конфигурацию без local fallback."""

    help = "Проверяет LDAP search, user bind и синхронизацию профиля Vektor."

    def add_arguments(self, parser: CommandParser) -> None:
        """Принять только несекретный идентификатор учётной записи."""
        parser.add_argument(
            "identifier",
            help="sAMAccountName или userPrincipalName тестового пользователя",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Запросить пароль скрыто и выполнить ровно LDAP backend."""
        if not settings.AUTH_LDAP_ENABLED:
            msg = "LDAP отключён: сначала задайте AUTH_LDAP_ENABLED=True и параметры клиента."
            raise CommandError(msg)

        password = getpass("Пароль тестовой LDAP-учётной записи: ")
        if not password:
            raise CommandError("Проверка LDAP отменена: пароль не введён.")

        try:
            backend = load_backend(LDAP_BACKEND)
            user = backend.authenticate(
                request=None,
                username=options["identifier"],
                password=password,
            )
        except (ImportError, RuntimeError) as error:
            msg = "LDAP backend не удалось загрузить; проверьте Linux-зависимости и конфигурацию."
            raise CommandError(msg) from error

        if user is None:
            msg = "Проверка LDAP не пройдена; проверьте endpoint, CA, Base DN и credentials."
            raise CommandError(msg)

        self.stdout.write(
            self.style.SUCCESS("Проверка LDAP успешно пройдена; профиль Vektor синхронизирован.")
        )
