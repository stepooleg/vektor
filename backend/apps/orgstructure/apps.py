"""Конфигурация приложения домена «Оргструктура, синхронизация с 1С:ЗУП» (AGENTS.md §5)."""

from django.apps import AppConfig


class OrgstructureConfig(AppConfig):
    """Конфигурация доменного приложения «orgstructure»."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.orgstructure"
    label = "orgstructure"
    verbose_name = "Оргструктура, синхронизация с 1С:ЗУП"
