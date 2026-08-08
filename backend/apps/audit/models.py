"""Модели audit-log (SPEC §12.3, 152-ФЗ).

Централизованный журнал всех действий над чувствительными данными (ПДн,
оценки, права, выгрузки). Каждая запись: кто (actor), когда (at), что
(action), над каким объектом (target_type/target_id), детали (details).

Записи неизменяемы (immutable) — append-only журнал. Хранение — не менее
срока хранения ПДн (DATA_RETENTION_MONTHS, SPEC §17 п.3).
"""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.users.models import User


class AuditLogEntry(models.Model):
    """Запись аудита действия над чувствительными данными (SPEC §12.3).

    ``action`` — категория действия (например, ``assessment.result.view``,
    ``user.permissions.change``, ``export.report``).
    ``target_type``/``target_id`` — тип и ID объекта, над которым выполнено
    действие (например, ``assessment.cycle`` / 42).
    ``details`` — JSON с контекстом (маскированные значения ПДн).
    """

    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_entries",
        verbose_name=_("Кто"),
    )
    action = models.CharField(_("Действие"), max_length=128, db_index=True)
    target_type = models.CharField(_("Тип объекта"), max_length=64, db_index=True)
    target_id = models.CharField(_("ID объекта"), max_length=64, null=True, blank=True)
    details = models.JSONField(_("Детали"), default=dict, blank=True)
    created_at = models.DateTimeField(_("Когда"), auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("Запись аудита")
        verbose_name_plural = _("Записи аудита")
        ordering = ["-created_at"]
        # Только чтение через ORM-сигналы (append-only) — см. services.py.

    def __str__(self) -> str:
        """Действие и актёр."""
        email = self.actor.email if (self.actor_id and self.actor) else "system"
        return f"[{self.action}] {email} → {self.target_type}:{self.target_id}"
