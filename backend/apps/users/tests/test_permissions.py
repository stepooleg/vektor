"""Тесты DRF permission-классов RBAC (Test-First, SPEC §2.2, AGENTS.md §9).

Контракты:
- HasPermission: доступ по коду разрешения (сумма по ролям);
- HasAnyRole: доступ по наличию роли;
- проверка анонима → отказ;
- доступ к чувствительным действиям будет журналироваться (audit — отдельный домен).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from apps.users.models import Permission, Role, User
from apps.users.permissions import HasAnyRole, HasPermission

if TYPE_CHECKING:
    from rest_framework.request import Request

UserModel = get_user_model()


def _make_user(email: str, *, roles: list[Role]) -> User:
    """Создать пользователя с ролями."""
    user = UserModel.objects.create_user(email=email, password="Strong-Pwd-1")
    if roles:
        user.roles.add(*roles)
    return user


def _attach_user(request: Request, user: object) -> Request:
    """Присоединить пользователя к запросу и вернуть его."""
    request.user = user  # type: ignore[assignment]  # Request.user — Any в drf-stubs
    return request


@pytest.fixture()
def role_with_perm() -> tuple[Role, Permission]:
    """Роль HR с разрешением assessment.cycle.view."""
    role = Role.objects.create(code=Role.Code.HR.value, name="HR")
    perm = Permission.objects.create(code="assessment.cycle.view", name="Просмотр циклов")
    role.permissions.add(perm)
    return role, perm


@pytest.mark.django_db
def test_has_permission_grants_for_authorized_user(
    rf_request: Request, role_with_perm: tuple[Role, Permission]
) -> None:
    """Пользователь с нужным разрешением получает доступ."""
    role, _ = role_with_perm
    user = _make_user("hr@corp.local", roles=[role])
    request = _attach_user(rf_request, user)

    class CanViewCycles(HasPermission):
        required_permission = "assessment.cycle.view"

    permission = CanViewCycles()
    assert permission.has_permission(request, view=None) is True


@pytest.mark.django_db
def test_has_permission_denies_for_user_without_permission(rf_request: Request) -> None:
    """Пользователь без разрешения получает отказ (минимум привилегий, SPEC §2.2)."""
    role_employee = Role.objects.create(code=Role.Code.EMPLOYEE.value, name="Сотрудник")
    user = _make_user("emp@corp.local", roles=[role_employee])
    request = _attach_user(rf_request, user)

    class CanViewCycles(HasPermission):
        required_permission = "assessment.cycle.view"

    permission = CanViewCycles()
    assert permission.has_permission(request, view=None) is False


@pytest.mark.django_db
def test_has_permission_denies_anonymous(rf_request: Request) -> None:
    """Анонимный пользователь — отказ (требуется аутентификация)."""
    request = _attach_user(rf_request, AnonymousUser())

    permission = HasPermission()
    assert permission.has_permission(request, view=None) is False


@pytest.mark.django_db
def test_has_any_role_grants_for_matching_role(rf_request: Request) -> None:
    """HasAnyRole: доступ при совпадении одной из ролей."""
    role_manager = Role.objects.create(code=Role.Code.MANAGER.value, name="Руководитель")
    user = _make_user("mgr@corp.local", roles=[role_manager])
    request = _attach_user(rf_request, user)

    permission = HasAnyRole(Role.Code.MANAGER.value, Role.Code.HR.value)
    assert permission.has_permission(request, view=None) is True


@pytest.mark.django_db
def test_has_any_role_denies_for_non_matching_role(rf_request: Request) -> None:
    """HasAnyRole: отказ, если ни одна роль не совпадает."""
    role_employee = Role.objects.create(code=Role.Code.EMPLOYEE.value, name="Сотрудник")
    user = _make_user("emp@corp.local", roles=[role_employee])
    request = _attach_user(rf_request, user)

    permission = HasAnyRole(Role.Code.MANAGER.value, Role.Code.HR.value)
    assert permission.has_permission(request, view=None) is False
