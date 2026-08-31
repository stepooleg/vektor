"""Celery-задачи политики хранения данных оценок (SPEC §12.6)."""

from __future__ import annotations

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .services import apply_assessment_retention


@shared_task(name="assessment.retention_daily")  # type: ignore[untyped-decorator]
def run_assessment_retention() -> dict[str, int | str]:
    """Ежедневно применить deployment-политику хранения данных оценок."""
    result = apply_assessment_retention(
        now=timezone.now(),
        retention_years=settings.DATA_RETENTION_YEARS,
        aggregate_mode=settings.ASSESSMENT_AGGREGATE_RETENTION_MODE,
    )
    return result.as_dict()
