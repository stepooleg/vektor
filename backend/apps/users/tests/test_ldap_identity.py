"""Контракт синхронизации LDAP-идентичности и RBAC (SPEC §10.2, issue #42)."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured

from apps.users.models import Role

UserModel = get_user_model()


def test_ldap_transport_rejects_plaintext_credentials_by_default() -> None:
    """LDAP bind не должен передавать пароль по незащищённому соединению."""
    from apps.users.ldap_config import validate_secure_transport

    with pytest.raises(ImproperlyConfigured, match="ldaps://"):
        validate_secure_transport(
            "ldap://dc.corp.local",
            start_tls=False,
            allow_insecure=False,
        )


def test_ldap_transport_accepts_ldaps_or_starttls() -> None:
    """LDAPS и LDAP с StartTLS считаются защищёнными вариантами."""
    from apps.users.ldap_config import validate_secure_transport

    validate_secure_transport("ldaps://dc.corp.local", start_tls=False, allow_insecure=False)
    validate_secure_transport("ldap://dc.corp.local", start_tls=True, allow_insecure=False)


def test_group_role_map_rejects_unknown_vektor_role() -> None:
    """Ошибка конфигурации не может создать произвольную привилегированную роль."""
    from apps.users.ldap_config import parse_group_role_map

    with pytest.raises(ImproperlyConfigured, match="unknown-admin"):
        parse_group_role_map('{"CN=Domain Admins,OU=Groups,DC=corp,DC=local": "unknown-admin"}')


@pytest.mark.django_db
def test_ldap_identity_maps_profile_and_only_allowlisted_group_roles() -> None:
    """LDAP-профиль обновляется, а роль выдаётся только через явный allowlist."""
    from apps.users.ldap_identity import sync_ldap_identity

    user = UserModel.objects.create_user(email="old@corp.local")
    employee_role = Role.objects.create(code=Role.Code.EMPLOYEE, name="Сотрудник")
    manual_hr_role = Role.objects.create(code=Role.Code.HR, name="HR")
    user.roles.add(manual_hr_role)

    sync_ldap_identity(
        user=user,
        username="a.ivanova",
        attributes={
            "mail": [b"alice.ivanova@corp.local"],
            "displayName": ["Алиса Иванова"],
            "thumbnailPhoto": [b"jpeg-binary"],
            "memberOf": [
                b"CN=Vektor-Employees,OU=Groups,DC=corp,DC=local",
                b"CN=Domain Admins,OU=Groups,DC=corp,DC=local",
            ],
        },
        group_role_map={
            "cn=vektor-employees,ou=groups,dc=corp,dc=local": "employee",
        },
    )

    user.refresh_from_db()
    assert user.email == "alice.ivanova@corp.local"
    assert user.first_name == "Алиса Иванова"
    assert user.ad_account == "a.ivanova"
    assert user.ad_thumbnail_photo is not None
    assert bytes(user.ad_thumbnail_photo) == b"jpeg-binary"
    assert set(user.roles.all()) == {employee_role, manual_hr_role}


@pytest.mark.django_db
def test_ldap_identity_does_not_revoke_manually_granted_mapped_role() -> None:
    """LDAP-маппинг не удаляет роль без явного признака LDAP-владения связью."""
    from apps.users.ldap_identity import sync_ldap_identity

    user = UserModel.objects.create_user(email="manager@corp.local")
    manager_role = Role.objects.create(code=Role.Code.MANAGER, name="Руководитель")
    user.roles.add(manager_role)

    sync_ldap_identity(
        user=user,
        username="manager",
        attributes={"memberOf": []},
        group_role_map={"cn=vektor-managers,dc=corp,dc=local": "manager"},
    )

    assert user.roles.filter(pk=manager_role.pk).exists()
