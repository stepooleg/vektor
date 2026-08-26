"""Интеграция Vektor backend с django-auth-ldap (Linux production/CI)."""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings

from apps.users.models import Role

django_auth_ldap = pytest.importorskip(
    "django_auth_ldap.backend",
    reason="python-ldap не поддерживает локальную Windows-среду",
)
VektorLDAPBackend = importlib.import_module("apps.users.ldap_backend").VektorLDAPBackend

UserModel = get_user_model()


@pytest.mark.django_db
@override_settings(
    AUTH_LDAP_GROUP_ROLE_MAP={
        "cn=vektor-employees,ou=groups,dc=corp,dc=local": "employee",
    }
)
def test_successful_ldap_bind_syncs_identity_and_allowlisted_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Успешный bind синхронизирует профиль и RBAC до создания сессии."""
    user = UserModel.objects.create_user(email="alice@corp.local")
    employee_role = Role.objects.create(code=Role.Code.EMPLOYEE, name="Сотрудник")
    ldap_user = SimpleNamespace(
        _username="a.ivanova",
        attrs={
            "mail": ["alice@corp.local"],
            "displayName": ["Алиса Иванова"],
            "memberOf": ["CN=Vektor-Employees,OU=Groups,DC=corp,DC=local"],
        },
    )
    monkeypatch.setattr(
        django_auth_ldap.LDAPBackend,
        "authenticate_ldap_user",
        lambda _backend, _ldap_user, _password: user,
    )

    authenticated_user = VektorLDAPBackend().authenticate_ldap_user(ldap_user, "secret")

    assert authenticated_user == user
    user.refresh_from_db()
    assert user.ad_account == "a.ivanova"
    assert list(user.roles.all()) == [employee_role]
