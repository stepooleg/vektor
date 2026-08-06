"""Celery-приложение Vektor (очереди/фон, SPEC §11.1).

Инициализируется в ``vektor/__init__`` при импорте проекта.
"""

from __future__ import annotations

import os

from celery import Celery, shared_task

# Модуль настроек по умолчанию — dev (prod переопределяет через env).
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vektor.settings.dev")

app = Celery("vektor")

# Конфигурация читается из Django-настроек (префикс CELERY_).
app.config_from_object("django.conf:settings", namespace="CELERY")

# Автообнаружение задач во всех приложениях: apps/<name>/tasks.py.
app.autodiscover_tasks()


@shared_task(bind=True, name="vektor.debug.ping")  # type: ignore[untyped-decorator]
def debug_ping(self: object) -> str:
    """Диагностическая задача: возвращает диагностический ответ."""
    _ = self
    return "pong"
