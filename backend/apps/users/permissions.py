"""DRF permission-классы для RBAC (SPEC §2.2, AGENTS.md §9).

Используются во всех доменных API для контроля доступа. Основа:
- разрешение (permission code) — гранулярное право (сумма по ролям пользователя);
- роль — бизнес-роль (HR/руководитель/сотрудник/методолог).

Все проверки идут через методы модели User (см. models.py), чтобы правило
«составные роли суммируют права» (SPEC §2.2) соблюдалось в одном месте.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rest_framework.permissions import BasePermission, IsAuthenticated

if TYPE_CHECKING:
    from rest_framework.request import Request

# Анонимные пользователи не допускаются — доступ только аутентифицированным.
# IsAuthenticated встроенный, но вынесен для читаемости комбинаций.
IsAuthenticatedUser = IsAuthenticated


class HasPermission(BasePermission):
    """Доступ по конкретному коду разрешения.

    Подклассы переопределяют ``required_permission``:
    ::

        class CanManageCycles(HasPermission):
            required_permission = "assessment.cycle.manage"
    """

    required_permission: str | None = None

    def has_permission(self, request: Request, view: object) -> bool:
        """True, если у пользователя есть требуемое разрешение."""
        user = request.user
        if user is None or not user.is_authenticated:
            return False
        if self.required_permission is None:
            msg = "HasPermission требует указать required_permission в подклассе"
            raise NotImplementedError(msg)
        return user.has_permission(self.required_permission)


class HasAnyRole(BasePermission):
    """Доступ при наличии хотя бы одной из перечисленных ролей.

    ::

        class HRorManager(HasAnyRole):
            required_roles = (Role.Code.HR.value, Role.Code.MANAGER.value)
    """

    required_roles: tuple[str, ...] = ()

    def __init__(self, *roles: str) -> None:
        """Допускает задание ролей как при наследовании, так и инлайн."""
        super().__init__()
        if roles:
            self.required_roles = roles

    def has_permission(self, request: Request, view: object) -> bool:
        """True, если у пользователя есть любая из требуемых ролей."""
        user = request.user
        if user is None or not user.is_authenticated:
            return False
        return user.has_any_role(*self.required_roles)


# ---- Готовые permission-наборы для типовых ролей (SPEC §2.1) ----
class IsHR(HasAnyRole):
    """Доступ только HR-администратору."""

    required_roles = ("hr",)


class IsManager(HasAnyRole):
    """Доступ только руководителю."""

    required_roles = ("manager",)


class IsMethodologist(HasAnyRole):
    """Доступ только методологу/куратору."""

    required_roles = ("methodologist",)
