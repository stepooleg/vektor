"""Конфигурационный контракт интеграции с 1С:ЗУП (issue #41)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest
from django.test import override_settings

from apps.orgstructure.onec_adapter import (
    OrgStructureSnapshot,
    RestOneCAdapter,
    get_onec_adapter,
)
from apps.orgstructure.tasks import sync_nightly


@override_settings(ONEC_SYNC_ENABLED=False)
def test_nightly_sync_is_safe_when_integration_is_disabled() -> None:
    """Выключенная интеграция не подменяется пустым снимком с архивацией."""
    with patch("apps.orgstructure.tasks.get_onec_adapter") as factory:
        result = sync_nightly()

    factory.assert_not_called()
    assert result == {"skipped": True}


@override_settings(
    ONEC_SYNC_ENABLED=True,
    ONEC_BASE_URL="https://onec.example.test/api",
    ONEC_AUTH_MODE="oauth",
    ONEC_USERNAME="",
    ONEC_PASSWORD="",
    ONEC_OAUTH_TOKEN="deployment-token",
    ONEC_TIMEOUT_SECONDS=20.0,
)
def test_factory_builds_rest_adapter_for_enabled_integration() -> None:
    """Включённая интеграция выбирает production REST-адаптер."""
    adapter = get_onec_adapter()

    assert isinstance(adapter, RestOneCAdapter)


@pytest.mark.django_db
@override_settings(ONEC_SYNC_ENABLED=True)
def test_nightly_sync_uses_last_successful_run_as_incremental_cursor() -> None:
    """Первый запуск полный, следующий передаёт cursor последней успешной попытки."""
    changed_since_values: list[datetime | None] = []

    class RecordingAdapter:
        def fetch_snapshot(self, *, changed_since: datetime | None = None) -> OrgStructureSnapshot:
            changed_since_values.append(changed_since)
            return OrgStructureSnapshot(
                departments=[],
                positions=[],
                employees=[],
                is_full=changed_since is None,
            )

    with patch("apps.orgstructure.tasks.get_onec_adapter", return_value=RecordingAdapter()):
        sync_nightly()
        sync_nightly()

    assert changed_since_values[0] is None
    assert changed_since_values[1] is not None
