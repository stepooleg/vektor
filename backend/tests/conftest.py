"""Общие фикстуры pytest для проекта Vektor.

Фикстура ``client`` использует DRF-совместимый тестовый клиент через
``APIClient`` — это даёт единый стиль для будущих API-тестов (AGENTS.md §3).
"""

from __future__ import annotations

import pytest
from django.test import Client
from rest_framework.test import APIClient


@pytest.fixture()
def client() -> Client:
    """Тестовый клиент Django (DRF APIClient как расширенная версия)."""
    return APIClient()
