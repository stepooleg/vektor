"""Celery-задачи синхронизации оргструктуры (SPEC §10.1).

Nightly-синхронизация (по расписанию Celery beat, см. ONEC_SYNC_CRON в .env) +
ручной запуск (через admin/management-команду).
"""

from __future__ import annotations

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import OneCSyncState
from .onec_adapter import get_onec_adapter
from .services import sync_orgstructure


@shared_task(name="orgstructure.sync_nightly")  # type: ignore[untyped-decorator]
def sync_nightly() -> dict[str, int | bool | list[str]]:
    """Nightly-синхронизация оргструктуры из 1С:ЗУП.

    Возвращает словарь со счётчиками результата для логирования/мониторинга.
    """
    if not settings.ONEC_SYNC_ENABLED:
        return {"skipped": True}

    started_at = timezone.now()
    state, _ = OneCSyncState.objects.get_or_create(pk=1)
    result = sync_orgstructure(get_onec_adapter(), changed_since=state.last_successful_at)
    state.last_successful_at = started_at
    state.save(update_fields=["last_successful_at"])
    return {
        "departments_created": result.departments_created,
        "departments_updated": result.departments_updated,
        "positions_created": result.positions_created,
        "positions_updated": result.positions_updated,
        "employees_created": result.employees_created,
        "employees_updated": result.employees_updated,
        "employees_archived": result.employees_archived,
        "errors": result.errors,
    }
