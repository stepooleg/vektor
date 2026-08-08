"""URL-конфигурация аналитики (подключается под /api/v1/analytics/)."""

from __future__ import annotations

from django.urls import path

from .views import CompanyDashboardView, EmployeeDashboardView

app_name = "analytics"

urlpatterns = [
    path(
        "employees/<int:employee_id>/dashboard/",
        EmployeeDashboardView.as_view(),
        name="employee-dashboard",
    ),
    path(
        "company-dashboard/",
        CompanyDashboardView.as_view(),
        name="company-dashboard",
    ),
]
