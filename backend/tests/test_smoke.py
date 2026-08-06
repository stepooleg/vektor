"""Smoke-тесты: Django-настройки грузятся и pytest-django корректно настроен.

Эти тесты защищают от регрессий конфигурации проекта (issue #1).
"""

from __future__ import annotations

from django.conf import settings


def test_django_settings_loaded() -> None:
    """Django-настройки инициализированы (SECRET_KEY задан)."""
    assert settings.SECRET_KEY


def test_installed_apps_contains_domains() -> None:
    """Все доменные приложения из AGENTS.md §5 зарегистрированы."""
    expected_domains = {
        "apps.users",
        "apps.orgstructure",
        "apps.competencies",
        "apps.assessment",
        "apps.feedback",
        "apps.portfolio",
        "apps.lms",
        "apps.idp",
        "apps.analytics",
        "apps.notifications",
        "apps.audit",
    }
    installed = set(settings.INSTALLED_APPS)
    missing = expected_domains - installed
    assert not missing, f"Отсутствуют доменные приложения: {missing}"


def test_rest_framework_and_spectacular_registered() -> None:
    """DRF и drf-spectacular включены (API-first, SPEC §11.2)."""
    installed = set(settings.INSTALLED_APPS)
    assert "rest_framework" in installed
    assert "drf_spectacular" in installed
