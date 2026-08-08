"""Сервисы audit-log (SPEC §12.3, §12.2, issue #33).

- ``log_action``: зафиксировать чувствительное действие (с маскированием ПДн);
- ``mask_pii``: маскирование email/телефонов в произвольном словаре;
- ``purge_expired_entries``: удаление записей по истечении срока хранения.

Журнал append-only: записи создаются через ``log_action`` и не меняются.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from .models import AuditLogEntry

if TYPE_CHECKING:
    from apps.users.models import User

# Паттерны ПДн для маскирования (SPEC §12.2 — маскирование в логах/UI).
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")
_PHONE_RE = re.compile(r"\+?\d[\d\s().-]{7,}\d")


def mask_pii(data: dict[str, Any]) -> dict[str, Any]:
    """Маскировать ПДн (email, телефон) в значениях словаря.

    Возвращает новый словарь с замаскированными значениями. Рекурсивно по
    вложенным dict; строки-значения сканируются на email/телефон.
    """
    masked: dict[str, Any] = {}
    for key, value in data.items():
        masked[key] = _mask_value(value)
    return masked


def _mask_value(value: Any) -> Any:
    """Маскировать одно значение (строка/email/телефон/словарь)."""
    if isinstance(value, str):
        v = _EMAIL_RE.sub("[email]", value)
        v = _PHONE_RE.sub("[phone]", v)
        return v
    if isinstance(value, dict):
        return {k: _mask_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_mask_value(v) for v in value]
    return value


def log_action(
    *,
    actor: User | None,
    action: str,
    target_type: str,
    target_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLogEntry:
    """Зафиксировать чувствительное действие в audit-log (SPEC §12.3).

    ПДн в ``details`` маскируются автоматически.
    """
    safe_details = mask_pii(details or {})
    return AuditLogEntry.objects.create(
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=safe_details,
    )


def purge_expired_entries(*, retention_months: int) -> int:
    """Удалить записи audit-log старше ``retention_months`` (SPEC §17 п.3).

    Возвращает число удалённых записей.
    """
    from datetime import timedelta

    from django.utils import timezone

    threshold = timezone.now() - timedelta(days=retention_months * 30)
    deleted, _ = AuditLogEntry.objects.filter(created_at__lt=threshold).delete()
    return deleted
