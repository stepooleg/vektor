"""Конфигурация приложения домена «Журнал достижений» (AGENTS.md §5)."""

from django.apps import AppConfig


class PortfolioConfig(AppConfig):
    """Конфигурация доменного приложения «portfolio»."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.portfolio"
    label = "portfolio"
    verbose_name = "Журнал достижений"
