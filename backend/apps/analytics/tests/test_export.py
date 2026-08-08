"""Тесты экспорта отчётов (Test-First, SPEC §9.5, issue #31).

Контракты:
- PDF генерируется с корректными данными;
- Excel содержит агрегаты;
- экспорт фиксируется в audit-log (§12.3);
- права — только уполномоченные роли (HR/руководитель).
"""

from __future__ import annotations

import pytest

from apps.analytics.export import (
    ExportNotAllowed,
    export_company_dashboard_pdf,
    export_company_dashboard_xlsx,
)
from apps.audit.models import AuditLogEntry
from apps.users.models import Role, User


def _user(email: str, role: str | None = None) -> User:
    """Создать пользователя с ролью."""
    user = User.objects.create_user(email=email, password="Strong-Pwd-1")
    if role:
        r, _ = Role.objects.get_or_create(code=role, defaults={"name": role})
        user.roles.add(r)
    return user


@pytest.mark.django_db
def test_export_pdf_generates_bytes() -> None:
    """PDF генерируется как байтовый поток (SPEC §9.5)."""
    hr = _user("hr@corp.local", Role.Code.HR.value)

    pdf_bytes = export_company_dashboard_pdf(actor=hr)

    assert pdf_bytes.startswith(b"%PDF")  # сигнатура PDF


@pytest.mark.django_db
def test_export_xlsx_generates_bytes() -> None:
    """Excel генерируется как байтовый поток (SPEC §9.5)."""
    hr = _user("hr@corp.local", Role.Code.HR.value)

    xlsx_bytes = export_company_dashboard_xlsx(actor=hr)

    # XLSX — zip-архив, начинается с PK.
    assert xlsx_bytes[:2] == b"PK"


@pytest.mark.django_db
def test_export_is_audited() -> None:
    """Каждая выгрузка фиксируется в audit-log (SPEC §12.3, §9.5)."""
    hr = _user("hr@corp.local", Role.Code.HR.value)

    export_company_dashboard_pdf(actor=hr)

    assert AuditLogEntry.objects.filter(
        action="export.report", target_type="analytics.dashboard"
    ).exists()


@pytest.mark.django_db
def test_export_denied_for_employee() -> None:
    """Сотрудник без прав не может экспортировать (§9.5, §2.2)."""
    emp = _user("emp@corp.local", Role.Code.EMPLOYEE.value)

    with pytest.raises(ExportNotAllowed):
        export_company_dashboard_pdf(actor=emp)
