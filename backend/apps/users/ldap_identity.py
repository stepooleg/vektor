"""Синхронизация подтверждённой LDAP-идентичности с пользователем Vektor."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from django.db import transaction

from .models import Role, User

LdapValue = str | bytes


def _first_text(attributes: Mapping[str, Sequence[LdapValue]], name: str) -> str:
    """Вернуть первое непустое LDAP-значение как UTF-8 строку."""
    values = attributes.get(name, ())
    if not values:
        return ""
    value = values[0]
    return value.decode("utf-8") if isinstance(value, bytes) else value


def _texts(attributes: Mapping[str, Sequence[LdapValue]], name: str) -> set[str]:
    """Вернуть нормализованное множество строк LDAP-атрибута."""
    return {
        (value.decode("utf-8") if isinstance(value, bytes) else value).strip().lower()
        for value in attributes.get(name, ())
        if value
    }


def _first_bytes(attributes: Mapping[str, Sequence[LdapValue]], name: str) -> bytes | None:
    """Вернуть первое LDAP-значение в бинарном виде."""
    values = attributes.get(name, ())
    if not values:
        return None
    value = values[0]
    return value if isinstance(value, bytes) else value.encode("utf-8")


@transaction.atomic
def sync_ldap_identity(
    *,
    user: User,
    username: str,
    attributes: Mapping[str, Sequence[LdapValue]],
    group_role_map: Mapping[str, str],
) -> User:
    """Обновить профиль и управляемые LDAP-роли после успешного bind.

    Неизвестные AD-группы игнорируются. Совпавшие роли добавляются, но не
    отзываются автоматически: без происхождения связи нельзя отличить роль,
    выданную LDAP, от назначенной вручную.
    """
    email = _first_text(attributes, "mail").strip().lower()
    display_name = _first_text(attributes, "displayName").strip()
    thumbnail_photo = _first_bytes(attributes, "thumbnailPhoto")

    if email:
        user.email = User.objects.normalize_email(email)
    if display_name:
        user.first_name = display_name
        user.last_name = ""
    user.ad_account = username.strip()
    if thumbnail_photo is not None:
        user.ad_thumbnail_photo = thumbnail_photo
    user.save(
        update_fields=[
            "email",
            "first_name",
            "last_name",
            "ad_account",
            "ad_thumbnail_photo",
        ]
    )

    normalized_map = {
        group_dn.strip().lower(): role_code for group_dn, role_code in group_role_map.items()
    }
    valid_role_codes = {choice.value for choice in Role.Code}
    matched_role_codes = {
        normalized_map[group_dn]
        for group_dn in _texts(attributes, "memberOf")
        if group_dn in normalized_map and normalized_map[group_dn] in valid_role_codes
    }

    if matched_role_codes:
        user.roles.add(*Role.objects.filter(code__in=matched_role_codes))
    return user
