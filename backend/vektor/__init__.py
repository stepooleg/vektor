"""Пакет проекта «Vektor».

Инициализирует Celery-приложение при импорте (см. ``vektor/celery.py``).
"""

from __future__ import annotations

__version__ = "0.1.0"

#: Версия API (используется в URL-конфигурации, ``/api/v1/``).
API_VERSION: str = "v1"

# Celery: импортируем приложение, чтобы оно было доступно через
# ``from vektor import celery_app`` и автозагрузчик задач сработал.
from .celery import app as celery_app  # noqa: E402  — side-effect import

__all__ = ["__version__", "API_VERSION", "celery_app"]
