"""Тесты MBO/OKR целеполагания (Test-First, SPEC v1.1 §16.4, issue #37).

Контракты:
- создание цели (Objective) с периодом;
- ключевой результат (KeyResult) считает прогресс (%);
- прогресс цели = средний прогресс KR;
- привязка цели к циклу оценки;
- завершённая цель — status=completed.
"""

from __future__ import annotations

import pytest

from apps.assessment.models import (
    AssessmentCycle,
    KeyResult,
    Objective,
)
from apps.orgstructure.models import Department, Employee, Position
from apps.users.models import User


def _employee(code: str, email: str) -> Employee:
    """Создать сотрудника."""
    dept = Department.objects.create(code_1c=f"D{code}", name=f"Отдел {code}")
    pos = Position.objects.create(code_1c=f"P{code}", name=f"Должность {code}")
    user = User.objects.create_user(email=email, password="Strong-Pwd-1")
    return Employee.objects.create(
        code_1c=code,
        user=user,
        last_name="И",
        first_name=code,
        department=dept,
        position=pos,
    )


@pytest.mark.django_db
def test_create_objective_with_period() -> None:
    """Создание цели с периодом Q1 (SPEC v1.1 §16.4)."""
    emp = _employee("E1", "e1@corp.local")
    obj = Objective.objects.create(
        employee=emp,
        title="Увеличить продажи",
        period=Objective.Period.Q1.value,
    )

    assert obj.status == Objective.Status.DRAFT.value
    assert obj.period == "Q1"


@pytest.mark.django_db
def test_key_result_progress_percent() -> None:
    """KR считает прогресс корректно (%)."""
    emp = _employee("E1", "e1@corp.local")
    obj = Objective.objects.create(employee=emp, title="Цель")
    kr = KeyResult.objects.create(
        objective=obj,
        title="KR1",
        target_value=200,
        current_value=50,
    )

    assert kr.progress_percent == 25  # 50/200 = 25%


@pytest.mark.django_db
def test_key_result_progress_capped_at_100() -> None:
    """Прогресс KR не превышает 100%."""
    emp = _employee("E1", "e1@corp.local")
    obj = Objective.objects.create(employee=emp, title="Цель")
    kr = KeyResult.objects.create(
        objective=obj,
        title="KR1",
        target_value=100,
        current_value=150,
    )

    assert kr.progress_percent == 100  # capped


@pytest.mark.django_db
def test_objective_progress_averages_krs() -> None:
    """Прогресс цели = средний прогресс KR (SPEC v1.1 §16.4)."""
    emp = _employee("E1", "e1@corp.local")
    obj = Objective.objects.create(employee=emp, title="Цель")
    KeyResult.objects.create(objective=obj, title="KR1", target_value=100, current_value=80)
    KeyResult.objects.create(objective=obj, title="KR2", target_value=100, current_value=40)

    assert obj.progress_percent == 60  # (80 + 40) / 2 = 60%


@pytest.mark.django_db
def test_objective_linked_to_cycle() -> None:
    """Цель привязана к циклу оценки (SPEC v1.1 §16.4)."""
    emp = _employee("E1", "e1@corp.local")
    cycle = AssessmentCycle.objects.create(name="Оценка 2026")
    obj = Objective.objects.create(
        employee=emp,
        title="Цель",
        cycle=cycle,
    )

    assert obj.cycle_id == cycle.id
    assert cycle.objectives.count() == 1


@pytest.mark.django_db
def test_completed_objective_status() -> None:
    """Завершённая цель — status=completed."""
    emp = _employee("E1", "e1@corp.local")
    obj = Objective.objects.create(
        employee=emp,
        title="Цель",
        status=Objective.Status.COMPLETED.value,
    )

    assert obj.status == Objective.Status.COMPLETED.value
