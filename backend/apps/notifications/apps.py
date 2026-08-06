"""Конфигурация приложения домена «Email и push, напоминания, эскалация» (AGENTS.md §5)."""

from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    """Конфигурация доменного приложения «notifications»."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notifications"
    label = "notifications"
    verbose_name = "Email и push, напоминания, эскалация"
