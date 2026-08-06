"""Регистрация моделей users в Django admin (для HR/администраторов)."""

from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import Permission, Role, RolePermission, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Конфигурация админки пользователя (вход по email, роли)."""

    ordering = ("email",)
    list_display = ("email", "ad_account", "is_active", "is_staff", "get_roles")
    list_filter = ("is_active", "is_staff", "roles")
    search_fields = ("email", "ad_account", "first_name", "last_name")
    filter_horizontal = ("roles", "groups", "user_permissions")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Корпоративная учётка"), {"fields": ("ad_account", "local_login_enabled")}),
        (_("Личные данные"), {"fields": ("first_name", "last_name")}),
        (_("Роли и права"), {"fields": ("roles", "groups", "user_permissions")}),
        (
            _("Статус"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "last_login",
                    "date_joined",
                )
            },
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2", "roles"),
            },
        ),
    )

    @admin.display(description=_("Роли"))
    def get_roles(self, obj: User) -> str:
        """Список кодов ролей пользователя."""
        return ", ".join(obj.roles.values_list("code", flat=True))


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """Админка ролей: предустановленные + редактируемые."""

    list_display = ("code", "name", "get_permissions_count")
    search_fields = ("code", "name")

    @admin.display(description=_("Разрешений"))
    def get_permissions_count(self, obj: Role) -> int:
        """Кол-во разрешений у роли."""
        return obj.permissions.count()


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    """Админка гранулярных разрешений."""

    list_display = ("code", "name")
    search_fields = ("code", "name")


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    """Админка связей роль-разрешение."""

    list_display = ("role", "permission")
    list_filter = ("role",)
