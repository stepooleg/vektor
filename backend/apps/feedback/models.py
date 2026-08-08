"""Модели непрерывной обратной связи (SPEC §6.1, §6.3).

Домен ``feedback`` — неформальная обратная связь между сотрудниками:
- ``Praise`` — благодарность/признание (публично/приватно/анонимно);
- ``FeedbackRequest`` — запрос обратной связи у выбранных коллег.

Анонимность (SPEC §6.3): отправитель может отправить ОС анонимно или от своего
имени; получатель видит отправителя только при ``is_anonymous=False``.
"""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.orgstructure.models import Employee


class Praise(models.Model):
    """Благодарность/признание коллеге (SPEC §6.1).

    - ``is_public=True`` — видна в общей ленте (публичная благодарность);
    - ``is_anonymous=True`` — отправитель скрыт (SPEC §6.3).
    """

    recipient = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="received_praises",
        verbose_name=_("Получатель"),
    )
    sender = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="sent_praises",
        verbose_name=_("Отправитель"),
    )
    message = models.TextField(_("Текст благодарности"))
    is_public = models.BooleanField(_("Публичная"), default=True)
    is_anonymous = models.BooleanField(_("Анонимная"), default=False)
    created_at = models.DateTimeField(_("Создано"), auto_now_add=True)

    class Meta:
        verbose_name = _("Благодарность")
        verbose_name_plural = _("Благодарности")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        """Краткое описание."""
        who = "аноним" if self.is_anonymous else str(self.sender)
        return f"{who} → {self.recipient}"


class FeedbackRequest(models.Model):
    """Запрос обратной связи у выбранных коллег (SPEC §6.1).

    Жизненный цикл: pending → answered / expired.
    """

    class Status(models.TextChoices):
        PENDING = "pending", _("Ожидает ответа")
        ANSWERED = "answered", _("Отвечено")
        EXPIRED = "expired", _("Просрочено")

    requester = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="feedback_requests_sent",
        verbose_name=_("Запросивший"),
    )
    recipient = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="feedback_requests_received",
        verbose_name=_("Получатель ОС"),
    )
    message = models.TextField(_("Что хотите обсудить?"), blank=True)
    status = models.CharField(
        _("Статус"), max_length=16, choices=Status.choices, default=Status.PENDING
    )
    created_at = models.DateTimeField(_("Создано"), auto_now_add=True)
    answered_at = models.DateTimeField(_("Отвечено"), null=True, blank=True)

    class Meta:
        verbose_name = _("Запрос обратной связи")
        verbose_name_plural = _("Запросы обратной связи")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        """Запросчик и получатель."""
        return f"{self.requester} → {self.recipient}"
