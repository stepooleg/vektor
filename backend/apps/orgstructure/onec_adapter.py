"""Адаптер интеграции с 1С:ЗУП (SPEC §10.1).

Тип интеграции уточняется с ИТ-службой заказчика (SPEC §17 п.1: REST/SOAP/файлы).
Поэтому реализован как абстракция (Protocol) с прототипом REST-адаптера и
фиктивным (in-memory) адаптером для тестов/разработки.

Односторонняя синхронизация: 1С → приложение. Источник правды по оргструктуре — 1С.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass(frozen=True)
class DepartmentDTO:
    """Данные подразделения из 1С (DTO для синхронизации)."""

    code_1c: str
    name: str
    parent_code_1c: str | None = None
    head_code_1c: str | None = None


@dataclass(frozen=True)
class PositionDTO:
    """Данные должности из 1С."""

    code_1c: str
    name: str


@dataclass(frozen=True)
class EmployeeDTO:
    """Данные сотрудника из 1С (ПДн — комплаенс 152-ФЗ)."""

    code_1c: str  # табельный номер
    email: str
    last_name: str
    first_name: str
    middle_name: str = ""
    department_code_1c: str = ""
    position_code_1c: str = ""
    manager_code_1c: str | None = None
    hire_date: str | None = None  # ISO-дата
    is_active: bool = True


@dataclass(frozen=True)
class OrgStructureSnapshot:
    """Снимок оргструктуры из 1С (все сущности за один запрос)."""

    departments: list[DepartmentDTO]
    positions: list[PositionDTO]
    employees: list[EmployeeDTO]


class OneCAdapter(Protocol):
    """Интерфейс адаптера 1С:ЗУП (расширяемая абстракция).

    Конкретные реализации: ``RestOneCAdapter`` (REST/OData), ``FileOneCAdapter``
    (обмен через XML/JSON-файлы), ``FakeOneCAdapter`` (тесты/разработка).
    """

    def fetch_snapshot(self) -> OrgStructureSnapshot:
        """Получить полный снимок оргструктуры из 1С."""
        ...


class FakeOneCAdapter:
    """Фиктивный адаптер для тестов/разработки (без реальной 1С).

    Возвращает снимок из переданных данных; в проде заменяется на реальный
    адаптер через фабрику ``get_onec_adapter()``.
    """

    def __init__(self, snapshot: OrgStructureSnapshot | None = None) -> None:
        """Создать адаптер с заданным снимком (по умолчанию — пустой)."""
        self._snapshot = snapshot or OrgStructureSnapshot(
            departments=[], positions=[], employees=[]
        )

    def fetch_snapshot(self) -> OrgStructureSnapshot:
        """Вернуть предзаготовленный снимок."""
        return self._snapshot


def get_onec_adapter() -> OneCAdapter:
    """Фабрика адаптера 1С (по ``ONEC_SYNC_ENABLED`` / ``ONEC_BASE_URL``).

    TODO(#8, SPEC §17 п.1): реализовать ``RestOneCAdapter`` после уточнения
    конфигурации 1С:ЗУП с ИТ-службой заказчика. Пока — ``FakeOneCAdapter``,
    чтобы синхронизация была тестируемой без реальной интеграции.
    """
    return FakeOneCAdapter()


def iter_subordinates_chain(employee_code: str, snapshot: OrgStructureSnapshot) -> Iterator[str]:
    """Вспомогательная функция: цепочка подчинённых кода сотрудника в снимке."""
    current: set[str] = {employee_code}
    while True:
        children = {
            e.code_1c
            for e in snapshot.employees
            if e.manager_code_1c in current and e.code_1c not in current
        }
        if not children:
            return
        current |= children
        yield from children
