"""Конфигурация приложения домена «Дашборды, агрегаты, экспорт» (AGENTS.md §5)."""

from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    """Конфигурация доменного приложения «analytics»."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.analytics"
    label = "analytics"
    verbose_name = "Дашборды, агрегаты, экспорт"
