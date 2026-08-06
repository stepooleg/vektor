"""Тесты синхронизации оргструктуры из 1С:ЗУП (Test-First, SPEC §3, §10.1).

Контракты (issue #8):
- синхронизация создаёт/обновляет/архивирует сотрудников;
- дерево отделов строится;
- перевод сотрудника переносит с указанием новых данных;
- увольнение архивирует профиль, сохраняя историю (is_active=False);
- повторная синхронизация идемпотентна;
- ошибки интеграции логируются и не ломают данные.
"""

from __future__ import annotations

import pytest

from apps.orgstructure.models import Department, Employee, Position
from apps.orgstructure.onec_adapter import (
    DepartmentDTO,
    EmployeeDTO,
    FakeOneCAdapter,
    OrgStructureSnapshot,
    PositionDTO,
)
from apps.orgstructure.services import sync_orgstructure
from apps.users.models import Role


def _snapshot(
    *,
    departments: list[DepartmentDTO] | None = None,
    positions: list[PositionDTO] | None = None,
    employees: list[EmployeeDTO] | None = None,
) -> OrgStructureSnapshot:
    """Собрать снимок оргструктуры."""
    return OrgStructureSnapshot(
        departments=departments or [],
        positions=positions or [],
        employees=employees or [],
    )


@pytest.fixture()
def _employee_role() -> Role:
    """Базовая роль сотрудника (нужна для создания User в sync)."""
    return Role.objects.create(code=Role.Code.EMPLOYEE.value, name="Сотрудник")


@pytest.mark.django_db
def test_sync_creates_departments_positions_employees(_employee_role: Role) -> None:
    """Синхронизация создаёт подразделения, должности и сотрудников."""
    snapshot = _snapshot(
        departments=[DepartmentDTO(code_1c="D1", name="ИТ")],
        positions=[PositionDTO(code_1c="P1", name="Разработчик")],
        employees=[
            EmployeeDTO(
                code_1c="E1",
                email="alice@corp.local",
                last_name="Иванова",
                first_name="Анна",
                department_code_1c="D1",
                position_code_1c="P1",
            )
        ],
    )

    result = sync_orgstructure(FakeOneCAdapter(snapshot))

    assert result.departments_created == 1
    assert result.positions_created == 1
    assert result.employees_created == 1
    assert Department.objects.count() == 1
    assert Position.objects.count() == 1
    emp = Employee.objects.get(code_1c="E1")
    assert emp.last_name == "Иванова"
    assert emp.department.code_1c == "D1"
    assert emp.position.code_1c == "P1"


@pytest.mark.django_db
def test_sync_builds_department_tree(_employee_role: Role) -> None:
    """Дерево подразделений строится по parent_code_1c."""
    snapshot = _snapshot(
        departments=[
            DepartmentDTO(code_1c="ROOT", name="Компания"),
            DepartmentDTO(code_1c="IT", name="ИТ", parent_code_1c="ROOT"),
            DepartmentDTO(code_1c="DEV", name="Разработка", parent_code_1c="IT"),
        ],
        positions=[PositionDTO(code_1c="P1", name="Сотрудник")],
        employees=[
            EmployeeDTO(
                code_1c="E1",
                email="x@corp.local",
                last_name="А",
                first_name="Б",
                department_code_1c="DEV",
                position_code_1c="P1",
            )
        ],
    )

    sync_orgstructure(FakeOneCAdapter(snapshot))

    dev = Department.objects.get(code_1c="DEV")
    assert dev.parent is not None
    assert dev.parent.code_1c == "IT"
    assert dev.parent.parent is not None
    assert dev.parent.parent.code_1c == "ROOT"


@pytest.mark.django_db
def test_sync_updates_existing_employee_on_transfer(_employee_role: Role) -> None:
    """Перевод сотрудника обновляет подразделение/должность."""
    snapshot1 = _snapshot(
        departments=[
            DepartmentDTO(code_1c="D1", name="ИТ"),
            DepartmentDTO(code_1c="D2", name="Бухгалтерия"),
        ],
        positions=[
            PositionDTO(code_1c="P1", name="Разработчик"),
            PositionDTO(code_1c="P2", name="Бухгалтер"),
        ],
        employees=[
            EmployeeDTO(
                code_1c="E1",
                email="alice@corp.local",
                last_name="Иванова",
                first_name="Анна",
                department_code_1c="D1",
                position_code_1c="P1",
            )
        ],
    )
    sync_orgstructure(FakeOneCAdapter(snapshot1))

    # Перевод в Бухгалтерию.
    snapshot2 = _snapshot(
        departments=snapshot1.departments,
        positions=snapshot1.positions,
        employees=[
            EmployeeDTO(
                code_1c="E1",
                email="alice@corp.local",
                last_name="Иванова",
                first_name="Анна",
                department_code_1c="D2",
                position_code_1c="P2",
            )
        ],
    )
    result = sync_orgstructure(FakeOneCAdapter(snapshot2))

    emp = Employee.objects.get(code_1c="E1")
    assert emp.department.code_1c == "D2"
    assert emp.position.code_1c == "P2"
    assert result.employees_updated == 1
    assert result.employees_created == 0


@pytest.mark.django_db
def test_sync_archives_fired_employee(_employee_role: Role) -> None:
    """Увольнение архивирует профиль (is_active=False), запись сохраняется (SPEC §3.4)."""
    snapshot1 = _snapshot(
        departments=[DepartmentDTO(code_1c="D1", name="ИТ")],
        positions=[PositionDTO(code_1c="P1", name="Разработчик")],
        employees=[
            EmployeeDTO(
                code_1c="E1",
                email="alice@corp.local",
                last_name="Иванова",
                first_name="Анна",
                department_code_1c="D1",
                position_code_1c="P1",
            )
        ],
    )
    sync_orgstructure(FakeOneCAdapter(snapshot1))

    # Сотрудник исчез из 1С → архивируем.
    snapshot2 = _snapshot(
        departments=snapshot1.departments,
        positions=snapshot1.positions,
        employees=[],
    )
    result = sync_orgstructure(FakeOneCAdapter(snapshot2))

    emp = Employee.objects.get(code_1c="E1")
    assert emp.is_active is False
    assert result.employees_archived == 1


@pytest.mark.django_db
def test_sync_is_idempotent(_employee_role: Role) -> None:
    """Повторная синхронизация того же снимка не создаёт дублей."""
    snapshot = _snapshot(
        departments=[DepartmentDTO(code_1c="D1", name="ИТ")],
        positions=[PositionDTO(code_1c="P1", name="Разработчик")],
        employees=[
            EmployeeDTO(
                code_1c="E1",
                email="alice@corp.local",
                last_name="Иванова",
                first_name="Анна",
                department_code_1c="D1",
                position_code_1c="P1",
            )
        ],
    )
    sync_orgstructure(FakeOneCAdapter(snapshot))
    result2 = sync_orgstructure(FakeOneCAdapter(snapshot))

    assert result2.departments_created == 0
    assert result2.positions_created == 0
    assert result2.employees_created == 0
    assert result2.employees_updated == 0
    assert Employee.objects.filter(code_1c="E1").count() == 1
    assert Department.objects.filter(code_1c="D1").count() == 1
