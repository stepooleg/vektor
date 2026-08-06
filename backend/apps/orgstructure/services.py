"""Сервис синхронизации оргструктуры из 1С:ЗУП (SPEC §10.1, §3.4).

Идемпотентный upsert по ``code_1c``:
- создаёт отсутствующие подразделения/должности/сотрудников;
- обновляет изменившиеся;
- архивирует исчезнувших из 1С сотрудников (``is_active=False``), сохраняя историю.

Сотруднику при создании автоматически создаётся User (если ещё нет) с ролью
«Сотрудник» (SPEC §2.1) — это связывает оргструктуру с RBAC.

Все ошибки интеграции логируются; частичный снимок не ломает целостность
(транзакция: либо все изменения, либо ни одного).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from django.db import transaction

from apps.users.models import Role, User

from .models import Department, Employee, Position
from .onec_adapter import (
    DepartmentDTO,
    EmployeeDTO,
    OneCAdapter,
    PositionDTO,
)

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Результат синхронизации: счётчики созданных/обновлённых/архивированных."""

    departments_created: int = 0
    departments_updated: int = 0
    positions_created: int = 0
    positions_updated: int = 0
    employees_created: int = 0
    employees_updated: int = 0
    employees_archived: int = 0
    errors: list[str] = field(default_factory=list)


@transaction.atomic
def sync_orgstructure(adapter: OneCAdapter) -> SyncResult:
    """Синхронизировать оргструктуру из 1С (через адаптер).

    Атомарная транзакция: при ошибке все изменения откатываются, данные БД
    остаются консистентными (SPEC §3 — источник правды 1С, не должно быть
    «полусинхронизированного» состояния).
    """
    result = SyncResult()
    snapshot = adapter.fetch_snapshot()

    # 1. Подразделения: сначала корневые, затем дочерние (многопроходно).
    dept_by_code: dict[str, Department] = {}
    _sync_departments(snapshot.departments, dept_by_code, result)

    # 2. Должности.
    pos_by_code: dict[str, Position] = {}
    for pos_dto in snapshot.positions:
        pos_by_code[pos_dto.code_1c] = _upsert_position(pos_dto, result)

    # 3. Сотрудники (upsert по code_1c, auto-User).
    emp_by_code: dict[str, Employee] = {}
    seen_codes: set[str] = set()
    for emp_dto in snapshot.employees:
        seen_codes.add(emp_dto.code_1c)
        department = dept_by_code.get(emp_dto.department_code_1c)
        position = pos_by_code.get(emp_dto.position_code_1c)
        if department is None or position is None:
            msg = (
                f"Сотрудник {emp_dto.code_1c}: пропущен "
                f"(department={emp_dto.department_code_1c}, position={emp_dto.position_code_1c})"
            )
            result.errors.append(msg)
            logger.warning(msg)
            continue
        manager = emp_by_code.get(emp_dto.manager_code_1c) if emp_dto.manager_code_1c else None
        emp_by_code[emp_dto.code_1c] = _upsert_employee(
            emp_dto, department=department, position=position, manager=manager, result=result
        )

    # 4. Дозаполняем руководителей вторым проходом (порядок в снимке произвольный).
    for emp_dto in snapshot.employees:
        if emp_dto.manager_code_1c and emp_dto.manager_code_1c in emp_by_code:
            emp = emp_by_code.get(emp_dto.code_1c)
            manager = emp_by_code[emp_dto.manager_code_1c]
            if emp and manager and emp.manager_id != manager.id:
                emp.manager = manager
                emp.save(update_fields=["manager"])

    # 5. Архивируем исчезнувших из 1С (SPEC §3.4 — сохраняем историю).
    missing = Employee.objects.exclude(code_1c__in=seen_codes).filter(is_active=True)
    result.employees_archived = missing.update(is_active=False)

    return result


def _sync_departments(
    dtos: list[DepartmentDTO],
    dept_by_code: dict[str, Department],
    result: SyncResult,
) -> None:
    """Синхронизировать дерево подразделений с разрешением родительских ссылок."""
    no_parent = [d for d in dtos if not d.parent_code_1c]
    with_parent = [d for d in dtos if d.parent_code_1c]

    for dto in no_parent:
        dept_by_code[dto.code_1c] = _upsert_department(dto, parent=None, result=result)

    remaining = list(with_parent)
    guard = 0
    while remaining and guard < len(dtos) + 1:
        guard += 1
        still: list[DepartmentDTO] = []
        for dto in remaining:
            parent = dept_by_code.get(dto.parent_code_1c or "")
            if parent is None:
                still.append(dto)
            else:
                dept_by_code[dto.code_1c] = _upsert_department(dto, parent=parent, result=result)
        if len(still) == len(remaining):
            # Неразрешённые ссылки (битые данные 1С) — логируем без прерывания.
            for dto in still:
                msg = f"Подразделение {dto.code_1c}: родитель {dto.parent_code_1c} не найден"
                result.errors.append(msg)
                logger.warning(msg)
            break
        remaining = still


def _upsert_department(
    dto: DepartmentDTO,
    *,
    parent: Department | None,
    result: SyncResult,
) -> Department:
    """Создать или обновить подразделение по code_1c."""
    dept = Department.objects.filter(code_1c=dto.code_1c).first()
    if dept is None:
        dept = Department.objects.create(code_1c=dto.code_1c, name=dto.name, parent=parent)
        result.departments_created += 1
        return dept

    changed = False
    if dept.name != dto.name:
        dept.name = dto.name
        changed = True
    if dept.parent_id != (parent.id if parent else None):
        dept.parent = parent
        changed = True
    if changed:
        dept.save()
        result.departments_updated += 1
    return dept


def _upsert_position(dto: PositionDTO, result: SyncResult) -> Position:
    """Создать или обновить должность по code_1c."""
    pos = Position.objects.filter(code_1c=dto.code_1c).first()
    if pos is None:
        pos = Position.objects.create(code_1c=dto.code_1c, name=dto.name)
        result.positions_created += 1
        return pos

    if pos.name != dto.name:
        pos.name = dto.name
        pos.save()
        result.positions_updated += 1
    return pos


def _upsert_employee(
    dto: EmployeeDTO,
    *,
    department: Department,
    position: Position,
    manager: Employee | None,
    result: SyncResult,
) -> Employee:
    """Создать или обновить сотрудника по code_1c (с auto-User)."""
    emp = Employee.objects.filter(code_1c=dto.code_1c).first()
    if emp is None:
        user = _ensure_user(dto)
        emp = Employee.objects.create(
            code_1c=dto.code_1c,
            user=user,
            last_name=dto.last_name,
            first_name=dto.first_name,
            middle_name=dto.middle_name,
            department=department,
            position=position,
            manager=manager,
            hire_date=dto.hire_date,
        )
        result.employees_created += 1
        return emp

    changed_fields: list[str] = []
    if emp.last_name != dto.last_name:
        emp.last_name = dto.last_name
        changed_fields.append("last_name")
    if emp.first_name != dto.first_name:
        emp.first_name = dto.first_name
        changed_fields.append("first_name")
    if emp.middle_name != dto.middle_name:
        emp.middle_name = dto.middle_name
        changed_fields.append("middle_name")
    if emp.department_id != department.id:
        emp.department = department
        changed_fields.append("department")
    if emp.position_id != position.id:
        emp.position = position
        changed_fields.append("position")
    if manager and emp.manager_id != manager.id:
        emp.manager = manager
        changed_fields.append("manager")
    if not emp.is_active:
        emp.is_active = True  # возвращён из архива
        changed_fields.append("is_active")
    if changed_fields:
        emp.save(update_fields=changed_fields)
        result.employees_updated += 1
    return emp


def _ensure_user(dto: EmployeeDTO) -> User:
    """Найти или создать User по email (связь оргструктура ↔ RBAC).

    Новому пользователю назначается роль «Сотрудник» (SPEC §2.1).
    Пароль не задаётся (вход через SSO); при необходимости HR задаёт локальный.
    """
    user, _ = User.objects.get_or_create(
        email=dto.email,
        defaults={"first_name": dto.first_name, "last_name": dto.last_name},
    )
    if not user.roles.exists():
        employee_role = Role.objects.filter(code=Role.Code.EMPLOYEE.value).first()
        if employee_role:
            user.roles.add(employee_role)
    return user
