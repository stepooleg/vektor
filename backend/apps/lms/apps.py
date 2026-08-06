"""Конфигурация приложения домена «Каталог курсов, уроки, тесты, задания» (AGENTS.md §5)."""

from django.apps import AppConfig


class LmsConfig(AppConfig):
    """Конфигурация доменного приложения «lms»."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.lms"
    label = "lms"
    verbose_name = "Каталог курсов, уроки, тесты, задания"
