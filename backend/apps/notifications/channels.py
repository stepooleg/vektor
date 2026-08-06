"""Каналы уведомлений (SPEC §13.1, §10.3).

Абстракция ``NotificationChannel`` (Protocol) + ``EmailChannel`` (SMTP через
``django.core.mail``). Push (PWA) добавится в Фазе 2 — отдельный канал.

needs-spec (#44, SPEC §17 п.4): SMTP-сервер/домен уточняются; реализация
читает конфигурацию из settings (EMAIL_HOST и т.д.), канал-агностична.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from django.conf import settings
from django.core.mail import send_mail

if TYPE_CHECKING:
    from .models import Notification


class NotificationChannel(Protocol):
    """Интерфейс канала уведомлений (расширяемая абстракция)."""

    def send(self, notification: Notification) -> None:
        """Отправить уведомление через канал."""
        ...


class EmailChannel:
    """Email-канал (основной, SPEC §13.1).

    Использует Django mail-backend (EMAIL_BACKEND): в проде — SMTP организации,
    в тестах — locmem. Шаблон письма — фирменный (BRANDBOOK §10.1).
    """

    def send(self, notification: Notification) -> None:
        """Отправить письмо и отметить уведомление как отправленное."""
        send_mail(
            subject=notification.subject,
            message=notification.body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@vektor.local"),
            recipient_list=[notification.recipient_email],
            fail_silently=False,
        )
        notification.mark_sent()


def get_email_channel() -> EmailChannel:
    """Фабрика email-канала (для DI/тестов)."""
    return EmailChannel()
