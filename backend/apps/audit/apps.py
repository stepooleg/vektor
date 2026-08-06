"""Конфигурация приложения домена «Audit log» (AGENTS.md §5)."""

from django.apps import AppConfig


class AuditConfig(AppConfig):
    """Конфигурация доменного приложения «audit»."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.audit"
    label = "audit"
    verbose_name = "Audit log"
