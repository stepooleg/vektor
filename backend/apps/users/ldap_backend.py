"""Backend прямой LDAP-аутентификации Active Directory (SPEC §10.2)."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django_auth_ldap.backend import LDAPBackend

from .ldap_identity import sync_ldap_identity
from .models import User


class VektorLDAPBackend(LDAPBackend):  # type: ignore[misc]
    """Выполняет bind через django-auth-ldap и синхронизирует профиль/RBAC."""

    def _load_thumbnail_photo(self, ldap_user: Any) -> bytes | None:
        """Прочитать бинарное фото отдельно от UTF-8 LDAPSearch."""
        try:
            results = ldap_user.connection.search_s(
                ldap_user.dn,
                self.ldap.SCOPE_BASE,
                "(objectClass=*)",
                ["thumbnailPhoto"],
            )
        except self.ldap.LDAPError:
            return None
        if not results:
            return None
        values = results[0][1].get("thumbnailPhoto", ())
        return values[0] if values and isinstance(values[0], bytes) else None

    def authenticate_ldap_user(self, ldap_user: Any, password: str) -> User | None:
        """Синхронизировать подтверждённую LDAP-идентичность после успешного bind."""
        user = super().authenticate_ldap_user(ldap_user, password)
        if not isinstance(user, User):
            return None
        attributes = dict(ldap_user.attrs or {})
        thumbnail_photo = self._load_thumbnail_photo(ldap_user)
        if thumbnail_photo is not None:
            attributes["thumbnailPhoto"] = [thumbnail_photo]
        return sync_ldap_identity(
            user=user,
            username=ldap_user._username,
            attributes=attributes,
            group_role_map=settings.AUTH_LDAP_GROUP_ROLE_MAP,
        )
