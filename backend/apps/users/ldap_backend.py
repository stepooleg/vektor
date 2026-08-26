"""Backend прямой LDAP-аутентификации Active Directory (SPEC §10.2)."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django_auth_ldap.backend import LDAPBackend

from .ldap_identity import sync_ldap_identity
from .models import User


class VektorLDAPBackend(LDAPBackend):  # type: ignore[misc]
    """Выполняет bind через django-auth-ldap и синхронизирует профиль/RBAC."""

    def authenticate_ldap_user(self, ldap_user: Any, password: str) -> User | None:
        """Синхронизировать подтверждённую LDAP-идентичность после успешного bind."""
        user = super().authenticate_ldap_user(ldap_user, password)
        if not isinstance(user, User):
            return None
        attributes = ldap_user.attrs or {}
        return sync_ldap_identity(
            user=user,
            username=ldap_user._username,
            attributes=attributes,
            group_role_map=settings.AUTH_LDAP_GROUP_ROLE_MAP,
        )
