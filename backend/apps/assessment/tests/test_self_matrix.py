"""Тесты самооценки и матрицы компетенций (Test-First, SPEC §5.1.2, §5.1.3, issue #11).

Контракты:
- самооценка сохраняется и входит в агрегат как группа ``self``;
- разрыв self vs others считается корректно;
- матрица возвращает текущий (из оценки) и ожидаемый (по роли) уровни;
- зоны развития — компетенции с текущим уровнем ниже ожидаемого.
"""

from __future__ import annotations

import pytest

from apps.assessment.matrix import (
    build_matrix,
    get_development_zones,
)
from apps.assessment.models import (
    AssessmentCycle,
    AssessmentResponse,
    ExpectedLevel,
    Participant,
    ReviewerAssignment,
)
from apps.assessment.services import (
    aggregate_cycle,
    get_self_vs_others_gap,
    mark_assignment_completed,
)
from apps.competencies.models import Competency, CompetencyGroup, Scale
from apps.orgstructure.models import Department, Employee, Position
from apps.users.models import User


def _make_employee(code: str, email: str) -> Employee:
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


def _make_competency(name: str = "К") -> Competency:
    """Компетенция со шкалой 1–5."""
    scale = Scale.objects.create(name=f"Шкала {name}", min_value=1, max_value=5)
    group = CompetencyGroup.objects.create(name=f"Группа {name}")
    return Competency.objects.create(name=name, group=group, scale=scale)


def _fill(assignment: ReviewerAssignment, competency: Competency, score: int) -> None:
    """Заполнить оценку и отметить завершённой."""
    AssessmentResponse.objects.create(assignment=assignment, competency=competency, score=score)
    mark_assignment_completed(assignment)


@pytest.mark.django_db
def test_self_assessment_enters_aggregate() -> None:
    """Самооценка сохраняется и видна в агрегате как группа self (SPEC §5.1.2)."""
    cycle = AssessmentCycle.objects.create(name="Цикл")
    emp = _make_employee("E1", "e1@corp.local")
    competency = _make_competency()
    participant = Participant.objects.create(cycle=cycle, employee=emp)

    # Обязательный менеджер.
    manager = _make_employee("M1", "m1@corp.local")
    a_mgr = ReviewerAssignment.objects.create(
        cycle=cycle,
        participant=participant,
        reviewer=manager,
        group=ReviewerAssignment.Group.MANAGER.value,
    )
    _fill(a_mgr, competency, 4)
    # Самооценка.
    a_self = ReviewerAssignment.objects.create(
        cycle=cycle,
        participant=participant,
        reviewer=emp,
        group=ReviewerAssignment.Group.SELF.value,
    )
    _fill(a_self, competency, 5)

    aggregate = aggregate_cycle(cycle)
    self_group = next(g for g in aggregate.groups if g.group == "self")

    assert self_group.participants_count == 1
    assert self_group.mean_score == 5.0


@pytest.mark.django_db
def test_self_vs_others_gap() -> None:
    """Разрыв self vs others считается как (self − среднее окружения)."""
    cycle = AssessmentCycle.objects.create(name="Цикл")
    emp = _make_employee("E1", "e1@corp.local")
    competency = _make_competency()
    participant = Participant.objects.create(cycle=cycle, employee=emp)

    manager = _make_employee("M1", "m1@corp.local")
    a_mgr = ReviewerAssignment.objects.create(
        cycle=cycle,
        participant=participant,
        reviewer=manager,
        group=ReviewerAssignment.Group.MANAGER.value,
    )
    _fill(a_mgr, competency, 3)
    a_self = ReviewerAssignment.objects.create(
        cycle=cycle,
        participant=participant,
        reviewer=emp,
        group=ReviewerAssignment.Group.SELF.value,
    )
    _fill(a_self, competency, 5)

    gap = get_self_vs_others_gap(participant, competency)

    # self=5, others (manager)=3 → gap=2.0 (сотрудник оценил себя выше).
    assert gap.self_score == 5.0
    assert gap.others_score == 3.0
    assert gap.gap == pytest.approx(2.0)


@pytest.mark.django_db
def test_matrix_current_vs_expected() -> None:
    """Матрица: текущий уровень (из оценки) vs ожидаемый по роли (SPEC §5.1.3)."""
    emp = _make_employee("E1", "e1@corp.local")
    competency = _make_competency()
    # Ожидаемый уровень по должности — 4 (выставляется HR/методологом).
    ExpectedLevel.objects.create(position=emp.position, competency=competency, expected_level=4)

    matrix = build_matrix(emp, current_levels={competency.id: 3})

    assert len(matrix.rows) == 1
    row = matrix.rows[0]
    assert row.competency_id == competency.id
    assert row.current_level == 3
    assert row.expected_level == 4


@pytest.mark.django_db
def test_development_zones_below_expected() -> None:
    """Зоны развития — компетенции с текущим уровнем ниже ожидаемого (SPEC §8.1)."""
    emp = _make_employee("E1", "e1@corp.local")
    c_low = _make_competency("Low")
    c_ok = _make_competency("Ok")
    ExpectedLevel.objects.create(position=emp.position, competency=c_low, expected_level=4)
    ExpectedLevel.objects.create(position=emp.position, competency=c_ok, expected_level=3)

    matrix = build_matrix(emp, current_levels={c_low.id: 2, c_ok.id: 4})
    zones = get_development_zones(matrix)

    assert {z.competency_id for z in zones} == {c_low.id}
    assert all(z.current_level < z.expected_level for z in zones)
