"""Модели уведомлений (SPEC §13).

- ``Notification`` — запись об уведомлении (событие, получатель, тело, статус);
- ``UserNotificationPreference`` — настройки пользователя (какие события и каналы,
  SPEC §13.3).

Каналы (email/push) абстрагированы через ``channels.py``; здесь — данные.
"""

from __future__ import annotations

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.users.models import User


class NotificationEvent(models.TextChoices):
    """События уведомлений (SPEC §13.2)."""

    ASSESSMENT_ASSIGNED = "assessment.assigned", _("Назначена оценка")
    ASSESSMENT_REMINDER = "assessment.reminder", _("Напоминание о дедлайне")
    ASSESSMENT_OVERDUE = "assessment.overdue", _("Просрочка оценки")
    ASSESSMENT_RESULT = "assessment.result", _("Итоговый отчёт по циклу")
    FEEDBACK_RECEIVED = "feedback.received", _("Получена обратная связь/благодарность")
    COURSE_ASSIGNED = "course.assigned", _("Назначен курс")
    COURSE_RESULT = "course.result", _("Результат проверки задания")
    MANUAL_BROADCAST = "manual.broadcast", _("Ручная рассылка HR")


class Notification(models.Model):
    """Запись об уведомлении (email/push-сообщение).

    ``sent_at`` — None, пока не отправлено. ``error`` — текст ошибки (для retry).
    """

    recipient_email = models.EmailField(_("Email получателя"))
    recipient_name = models.CharField(_("Имя получателя"), max_length=255, blank=True)
    event = models.CharField(_("Событие"), max_length=64, choices=NotificationEvent.choices)
    subject = models.CharField(_("Тема"), max_length=255)
    body = models.TextField(_("Тело"))
    created_at = models.DateTimeField(_("Создано"), auto_now_add=True)
    sent_at = models.DateTimeField(_("Отправлено"), null=True, blank=True)
    error = models.TextField(_("Ошибка"), blank=True)

    class Meta:
        verbose_name = _("Уведомление")
        verbose_name_plural = _("Уведомления")
        ordering = ["-created_at"]
        # Индекс для anti-spam-проверки (поиск по event+email+sent_at).
        indexes = [
            models.Index(fields=["event", "recipient_email"], name="notif_event_email_idx"),
        ]

    def __str__(self) -> str:
        """Тема и получатель."""
        return f"{self.subject} → {self.recipient_email}"

    def mark_sent(self) -> None:
        """Отметить уведомление как отправленное."""
        self.sent_at = timezone.now()
        self.save(update_fields=["sent_at"])

    def mark_failed(self, error: str) -> None:
        """Зафиксировать ошибку отправки (для retry-логики)."""
        self.error = error
        self.save(update_fields=["error"])


class UserNotificationPreference(models.Model):
    """Настройки уведомлений пользователя (SPEC §13.3).

    По умолчанию все каналы включены; пользователь может отключить отдельные
    события/каналы (в рамках допустимого — ручные рассылки HR всегда проходят).
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
        verbose_name=_("Пользователь"),
    )
    event = models.CharField(_("Событие"), max_length=64, choices=NotificationEvent.choices)
    email_enabled = models.BooleanField(_("Email включён"), default=True)
    push_enabled = models.BooleanField(_("Push включён"), default=True)

    class Meta:
        verbose_name = _("Настройка уведомлений")
        verbose_name_plural = _("Настройки уведомлений")
        unique_together = [("user", "event")]

    def __str__(self) -> str:
        """Пользователь и событие."""
        return f"{self.user.email} — {self.event}"


class PushSubscription(models.Model):
    """Подписка пользователя на Web Push (SPEC §10.4).

    Хранит endpoint и ключи подписки (P-256h, Auth). Один пользователь может
    иметь несколько подписок (разные устройства/браузеры).
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
        verbose_name=_("Пользователь"),
    )
    endpoint = models.URLField(_("Endpoint подписки"), max_length=500)
    p256dh = models.CharField(_("P-256dh ключ"), max_length=200)
    auth = models.CharField(_("Auth ключ"), max_length=200)
    created_at = models.DateTimeField(_("Создана"), auto_now_add=True)
    is_active = models.BooleanField(_("Активна"), default=True)

    class Meta:
        verbose_name = _("Push-подписка")
        verbose_name_plural = _("Push-подписки")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        """Email пользователя и статус."""
        return f"Push: {self.user.email} ({'✓' if self.is_active else '✗'})"
