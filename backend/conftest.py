"""Корневой conftest — общие фикстуры для ВСЕХ тестов (tests/ и apps/).

Дублирует/расширяет tests/conftest.py, чтобы фикстуры были видны и доменным
тестам в apps/*/.tests/. Размещение в корне backend/ гарантирует, что pytest
подхватит их для любого testpath.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.test import APIClient


@pytest.fixture()
def client() -> APIClient:
    """DRF-совместимый тестовый клиент (APIClient)."""
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture()
def rf_request() -> Request:
    """«Голый» DRF-запрос для тестирования permission-классов и функций.

    В permission-тестах request.user подменяется вручную.
    """
    from rest_framework.test import APIRequestFactory

    factory = APIRequestFactory()
    return factory.get("/")


@pytest.fixture(autouse=True)
def _flush_cache() -> Iterator[None]:
    """Очищать кеш между тестами (изоляция счётчиков lockout и т.п.)."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()
