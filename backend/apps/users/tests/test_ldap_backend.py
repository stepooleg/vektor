"""Автономный контракт Vektor с django-auth-ldap (Linux production/CI)."""

from __future__ import annotations

import importlib
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings

from apps.users.models import Role

ldap = pytest.importorskip(
    "ldap",
    reason="python-ldap не поддерживает локальную Windows-среду",
)
LDAPSearch = pytest.importorskip("django_auth_ldap.config").LDAPSearch
VektorLDAPBackend = importlib.import_module("apps.users.ldap_backend").VektorLDAPBackend

UserModel = get_user_model()
USER_DN = "cn=alice ivanova,ou=people,dc=corp,dc=local"


class FakeActiveDirectoryConnection:
    """Минимальный протокол python-ldap для проверки search → user bind."""

    def __init__(self) -> None:
        self.binds: list[tuple[str, str]] = []
        self.searches: list[tuple[str, int, str, list[str] | None]] = []

    def set_option(self, _option: int, _value: object) -> None:
        """Принять TLS options так же, как LDAPObject."""

    def start_tls_s(self) -> None:
        """Поддержать конфигурацию StartTLS."""

    def simple_bind_s(self, bind_dn: str, password: str) -> None:
        """Принять service bind и проверить пароль пользователя."""
        self.binds.append((bind_dn, password))
        if bind_dn.lower() == USER_DN and password != "Corporate-Pwd-12345":
            raise ldap.INVALID_CREDENTIALS

    def search_s(
        self,
        base_dn: str,
        scope: int,
        filterstr: str,
        attrlist: list[str] | None,
    ) -> list[tuple[str, dict[str, list[bytes]]]]:
        """Вернуть известную AD-запись или её бинарное фото."""
        self.searches.append((base_dn, scope, filterstr, attrlist))
        if scope == ldap.SCOPE_BASE:
            return [(USER_DN, {"thumbnailPhoto": [b"\xff\xd8jpeg-binary"]})]
        return [
            (
                USER_DN,
                {
                    "mail": [b"alice@corp.local"],
                    "displayName": ["Алиса Иванова".encode()],
                    "memberOf": [b"CN=Vektor-Employees,OU=Groups,DC=corp,DC=local"],
                },
            )
        ]


@pytest.mark.django_db
@override_settings(
    AUTH_LDAP_SERVER_URI="ldaps://fake-ad.local",
    AUTH_LDAP_BIND_DN="cn=vektor-reader,dc=corp,dc=local",
    AUTH_LDAP_BIND_PASSWORD="reader-password",
    AUTH_LDAP_START_TLS=False,
    AUTH_LDAP_CONNECTION_OPTIONS={},
    AUTH_LDAP_USER_SEARCH=LDAPSearch(
        "ou=people,dc=corp,dc=local",
        ldap.SCOPE_SUBTREE,
        "(|(sAMAccountName=%(user)s)(userPrincipalName=%(user)s))",
        attrlist=["mail", "displayName", "memberOf"],
    ),
    AUTH_LDAP_USER_QUERY_FIELD="email",
    AUTH_LDAP_USER_ATTR_MAP={"email": "mail", "first_name": "displayName"},
    AUTH_LDAP_ALWAYS_UPDATE_USER=True,
    AUTH_LDAP_GROUP_ROLE_MAP={
        "cn=vektor-employees,ou=groups,dc=corp,dc=local": "employee",
    },
)
def test_full_ldap_contract_searches_binds_and_syncs_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Без внешнего AD проверяется реальная цепочка библиотеки до модели Vektor."""
    connection = FakeActiveDirectoryConnection()
    backend = VektorLDAPBackend()
    monkeypatch.setattr(
        backend.ldap,
        "initialize",
        lambda _uri, **_kwargs: connection,
    )
    employee_role = Role.objects.create(code=Role.Code.EMPLOYEE, name="Сотрудник")

    user = backend.authenticate(
        request=None,
        username="a.ivanova",
        password="Corporate-Pwd-12345",
    )

    assert user is not None
    user.refresh_from_db()
    assert user.email == "alice@corp.local"
    assert user.ad_account == "a.ivanova"
    assert bytes(user.ad_thumbnail_photo or b"") == b"\xff\xd8jpeg-binary"
    assert list(user.roles.all()) == [employee_role]
    assert connection.binds == [
        ("cn=vektor-reader,dc=corp,dc=local", "reader-password"),
        (USER_DN, "Corporate-Pwd-12345"),
        ("cn=vektor-reader,dc=corp,dc=local", "reader-password"),
    ]
    assert "(sAMAccountName=a.ivanova)" in connection.searches[0][2]
    assert connection.searches[-1][1] == ldap.SCOPE_BASE


@pytest.mark.django_db
def test_wrong_directory_password_does_not_create_user(
    monkeypatch: pytest.MonkeyPatch,
    settings: Any,
) -> None:
    """Отказ user bind не создаёт локальную учётную запись."""
    settings.AUTH_LDAP_SERVER_URI = "ldaps://fake-ad.local"
    settings.AUTH_LDAP_BIND_DN = "cn=vektor-reader,dc=corp,dc=local"
    settings.AUTH_LDAP_BIND_PASSWORD = "reader-password"
    settings.AUTH_LDAP_CONNECTION_OPTIONS = {}
    settings.AUTH_LDAP_USER_SEARCH = LDAPSearch(
        "ou=people,dc=corp,dc=local",
        ldap.SCOPE_SUBTREE,
        "(sAMAccountName=%(user)s)",
        attrlist=["mail", "displayName", "memberOf"],
    )
    connection = FakeActiveDirectoryConnection()
    backend = VektorLDAPBackend()
    monkeypatch.setattr(
        backend.ldap,
        "initialize",
        lambda _uri, **_kwargs: connection,
    )

    user = backend.authenticate(
        request=None,
        username="a.ivanova",
        password="wrong-password",
    )

    assert user is None
    assert not UserModel.objects.exists()
