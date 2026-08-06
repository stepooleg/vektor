"""Тесты модели компетенций (Test-First, SPEC §4, issue #9).

Контракты:
- создание группы/компетенции/шкалы;
- шкала валидирует диапазон (contains);
- поведенческие индикаторы по уровням;
- привязка модели компетенций (корпоративная/ролевая/индивидуальная).
"""

from __future__ import annotations

import pytest

from apps.competencies.models import (
    Competency,
    CompetencyFramework,
    CompetencyGroup,
    Indicator,
    Scale,
)
from apps.orgstructure.models import Department, Employee, Position
from apps.users.models import User


def _department_and_position() -> tuple[Department, Position]:
    """Создать подразделение и должность (для ролевой привязки)."""
    dept = Department.objects.create(code_1c="D1", name="ИТ")
    pos = Position.objects.create(code_1c="P1", name="Разработчик")
    return dept, pos


@pytest.mark.django_db
def test_create_group_competency_scale() -> None:
    """Создание группы, компетенции и шкалы (SPEC §4.1)."""
    scale = Scale.objects.create(name="1–5", min_value=1, max_value=5)
    group = CompetencyGroup.objects.create(name="Лидерство")
    competency = Competency.objects.create(name="Принятие решений", group=group, scale=scale)

    assert competency.scale.max_value == 5
    assert competency.group.name == "Лидерство"


@pytest.mark.django_db
def test_scale_validates_range() -> None:
    """Шкала валидирует попадание значения в диапазон (1–5 / 1–10)."""
    scale = Scale.objects.create(name="Шкала", min_value=1, max_value=5)

    assert scale.contains(1)
    assert scale.contains(5)
    assert not scale.contains(0)
    assert not scale.contains(6)


@pytest.mark.django_db
def test_indicators_per_level() -> None:
    """Поведенческие индикаторы по уровням шкалы (для калибровки)."""
    scale = Scale.objects.create(name="1–3", min_value=1, max_value=3)
    group = CompetencyGroup.objects.create(name="Группа")
    competency = Competency.objects.create(name="К", group=group, scale=scale)
    Indicator.objects.create(competency=competency, level=1, description="Базовый")
    Indicator.objects.create(competency=competency, level=3, description="Экспертный")

    levels = {i.level for i in competency.indicators.all()}
    assert levels == {1, 3}


@pytest.mark.django_db
def test_framework_corporate_scope() -> None:
    """Корпоративная модель — общая для всех (SPEC §4.3)."""
    fw = CompetencyFramework.objects.create(
        name="Корпоративные ценности", scope=CompetencyFramework.Scope.CORPORATE.value
    )
    assert fw.scope == CompetencyFramework.Scope.CORPORATE.value
    assert fw.position is None
    assert fw.employee is None


@pytest.mark.django_db
def test_framework_role_scope_linked_to_position() -> None:
    """Ролевая модель привязана к должности (SPEC §4.3)."""
    _, pos = _department_and_position()
    fw = CompetencyFramework.objects.create(
        name="Для разработчиков",
        scope=CompetencyFramework.Scope.ROLE.value,
        position=pos,
    )
    assert fw.position_id == pos.id


@pytest.mark.django_db
def test_framework_individual_scope_linked_to_employee() -> None:
    """Индивидуальная модель привязана к сотруднику (SPEC §4.3)."""
    dept, pos = _department_and_position()
    user = User.objects.create_user(email="e@corp.local", password="Strong-Pwd-1")
    emp = Employee.objects.create(
        code_1c="E1", user=user, last_name="А", first_name="Б", department=dept, position=pos
    )
    fw = CompetencyFramework.objects.create(
        name="Индивидуальный план",
        scope=CompetencyFramework.Scope.INDIVIDUAL.value,
        employee=emp,
    )
    assert fw.employee_id == emp.id
