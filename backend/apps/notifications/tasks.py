"""Celery-задачи уведомлений (SPEC §13).

Асинхронная отправка с retry при ошибке SMTP. В тестах Celery eager
(см. settings.test.py) — выполняется синхронно.
"""

from __future__ import annotations

from celery import shared_task

from .channels import get_email_channel
from .models import Notification


@shared_task(  # type: ignore[untyped-decorator]
    name="notifications.send",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def send_notification_task(self, notification_id: int) -> None:  # type: ignore[no-untyped-def]
    """Отправить уведомление по ID с retry при ошибке.

    Retry: экспоненциальный backoff до 5 попыток (SPEC §10.3 — надёжность).
    """
    notification = Notification.objects.filter(id=notification_id).first()
    if notification is None or notification.sent_at is not None:
        return  # уже отправлено или удалено — идемпотентно
    try:
        channel = get_email_channel()
        channel.send(notification)
    except Exception as exc:
        notification.mark_failed(str(exc))
        raise
