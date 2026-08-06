"""Тесты health-check эндпоинта ``/api/v1/health/`` (Test-First, AGENTS.md §3).

Пишутся ДО реализации поведения и фиксируют контракт:
- 200 OK;
- JSON со статусом ``ok``;
- присутствует версия API и приложения.
"""

from __future__ import annotations

import pytest
from django.test import Client
from rest_framework import status


@pytest.mark.django_db
def test_health_endpoint_returns_ok(client: Client) -> None:
    """``GET /api/v1/health/`` отвечает 200 и ``status == "ok"``."""
    response = client.get("/api/v1/health/")

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["status"] == "ok"


@pytest.mark.django_db
def test_health_endpoint_reports_versions(client: Client) -> None:
    """В ответе есть версия приложения и версия API."""
    response = client.get("/api/v1/health/")

    body = response.json()
    assert "version" in body
    assert isinstance(body["version"], str) and body["version"]
    assert body["api_version"] == "v1"
