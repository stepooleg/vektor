"""Конфигурация приложения домена «Модель компетенций» (AGENTS.md §5)."""

from django.apps import AppConfig


class CompetenciesConfig(AppConfig):
    """Конфигурация доменного приложения «competencies»."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.competencies"
    label = "competencies"
    verbose_name = "Модель компетенций"
