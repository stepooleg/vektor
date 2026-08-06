"""Конфигурация приложения домена «Циклы оценки 360°, самооценка, матрица» (AGENTS.md §5)."""

from django.apps import AppConfig


class AssessmentConfig(AppConfig):
    """Конфигурация доменного приложения «assessment»."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.assessment"
    label = "assessment"
    verbose_name = "Циклы оценки 360°, самооценка, матрица"
