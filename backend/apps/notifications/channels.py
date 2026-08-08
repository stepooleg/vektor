"""Каналы уведомлений (SPEC §13.1, §10.3, §10.4).

Абстракция ``NotificationChannel`` (Protocol), ``EmailChannel`` (SMTP) и
``PushChannel`` (Web Push + VAPID, SPEC §10.4).

needs-spec (#44, SPEC §17 п.4): SMTP-сервер/домен уточняются; реализация
читает конфигурацию из settings (EMAIL_HOST и т.д.), канал-агностична.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Protocol

from django.conf import settings
from django.core.mail import send_mail
from pywebpush import webpush

if TYPE_CHECKING:
    from apps.users.models import User

    from .models import Notification

logger = logging.getLogger(__name__)


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


class PushChannel:
    """Push-канал (Web Push + VAPID, SPEC §10.4).

    Отправляет push-уведомления всем активным подпискам пользователя.
    VAPID-ключи из settings (VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY / VAPID_SUBJECT).
    """

    def send_to_user(self, user: User, payload: dict[str, str]) -> int:
        """Отправить push всем активным подпискам пользователя.

        Возвращает число успешно отправленных (ошибки логируются, не прерывают).
        """
        # Локальный импорт, чтобы избежать циклической зависимости.
        from .models import PushSubscription

        subscriptions = PushSubscription.objects.filter(user=user, is_active=True)
        sent = 0
        for sub in subscriptions:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                    },
                    data=json.dumps(payload),
                    vapid_private_key=getattr(settings, "VAPID_PRIVATE_KEY", ""),
                    vapid_claims={
                        "sub": getattr(settings, "VAPID_SUBJECT", "mailto:no-reply@vektor.local")
                    },
                )
                sent += 1
            except Exception:
                logger.warning("Push failed for %s", sub.endpoint, exc_info=True)
        return sent


def get_push_channel() -> PushChannel:
    """Фабрика push-канала."""
    return PushChannel()
