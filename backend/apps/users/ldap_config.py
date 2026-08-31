"""Безопасный разбор конфигурации LDAP без доступа к Django ORM."""

from __future__ import annotations

import json

from django.core.exceptions import ImproperlyConfigured

_ROLE_CODES = frozenset({"hr", "manager", "employee", "methodologist"})


def validate_secure_transport(
    server_uri: str,
    *,
    start_tls: bool,
    allow_insecure: bool,
) -> None:
    """Запретить передачу LDAP-учётных данных без TLS по умолчанию."""
    secure = server_uri.lower().startswith("ldaps://") or (
        server_uri.lower().startswith("ldap://") and start_tls
    )
    if not secure and not allow_insecure:
        msg = (
            "LDAP требует ldaps:// или AUTH_LDAP_START_TLS=True; "
            "небезопасный transport разрешается только явным dev-флагом."
        )
        raise ImproperlyConfigured(msg)


def parse_group_role_map(raw: str) -> dict[str, str]:
    """Разобрать JSON allowlist ``DN группы → код роли Vektor``."""
    if not raw.strip():
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        msg = "AUTH_LDAP_GROUP_ROLE_MAP должен быть корректным JSON-объектом."
        raise ImproperlyConfigured(msg) from error
    if not isinstance(value, dict) or not all(
        isinstance(group_dn, str) and isinstance(role_code, str)
        for group_dn, role_code in value.items()
    ):
        msg = "AUTH_LDAP_GROUP_ROLE_MAP должен содержать строковые пары DN и роли."
        raise ImproperlyConfigured(msg)

    unknown_roles = sorted(set(value.values()) - _ROLE_CODES)
    if unknown_roles:
        msg = f"AUTH_LDAP_GROUP_ROLE_MAP содержит неизвестные роли: {', '.join(unknown_roles)}"
        raise ImproperlyConfigured(msg)

    return {group_dn.strip().lower(): role_code for group_dn, role_code in value.items()}
