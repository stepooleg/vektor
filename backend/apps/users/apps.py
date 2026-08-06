"""Конфигурация приложения домена «Пользователи, RBAC, SSO/LDAP» (AGENTS.md §5)."""

from django.apps import AppConfig


class UsersConfig(AppConfig):
    """Конфигурация доменного приложения «users»."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.users"
    label = "users"
    verbose_name = "Пользователи, RBAC, SSO/LDAP"
