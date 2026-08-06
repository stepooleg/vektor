"""Конфигурация приложения домена «Индивидуальные планы развития» (AGENTS.md §5)."""

from django.apps import AppConfig


class IdpConfig(AppConfig):
    """Конфигурация доменного приложения «idp»."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.idp"
    label = "idp"
    verbose_name = "Индивидуальные планы развития"
