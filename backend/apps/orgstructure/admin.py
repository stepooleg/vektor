"""Регистрация моделей orgstructure в Django admin."""

from __future__ import annotations

from django.contrib import admin

from .models import Department, Employee, Position


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    """Админка подразделений."""

    list_display = ("name", "code_1c", "parent", "head", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code_1c")


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    """Админка должностей."""

    list_display = ("name", "code_1c")
    search_fields = ("name", "code_1c")


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    """Админка сотрудников."""

    list_display = (
        "full_name",
        "code_1c",
        "department",
        "position",
        "manager",
        "is_active",
        "assessment_eligible",
    )
    list_filter = ("is_active", "assessment_eligible", "department")
    search_fields = ("last_name", "first_name", "middle_name", "code_1c", "user__email")
