"""Конфигурация приложения домена «Непрерывная обратная связь, благодарности» (AGENTS.md §5)."""

from django.apps import AppConfig


class FeedbackConfig(AppConfig):
    """Конфигурация доменного приложения «feedback»."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.feedback"
    label = "feedback"
    verbose_name = "Непрерывная обратная связь, благодарности"
