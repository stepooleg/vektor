"""Тесты анонимности 360° (Test-First, SPEC §6.3, §12, 152-ФЗ — КРИТИЧНО).

Контракты (issue #12):
- API/сервисы НЕ возвращают сырые ответы отдельных оценщиков;
- группа < порога не возвращается в результате (hidden_by_threshold);
- HR получает только агрегаты по группам;
- попытка обойти порог через разные запросы не деанонимизирует.
"""

from __future__ import annotations

import pytest

from apps.assessment.models import (
    AssessmentCycle,
    AssessmentResponse,
    Participant,
    ReviewerAssignment,
)
from apps.assessment.services import aggregate_cycle, mark_assignment_completed
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


def _make_competency() -> Competency:
    """Компетенция со шкалой 1–5."""
    scale = Scale.objects.create(name="Шкала", min_value=1, max_value=5)
    group = CompetencyGroup.objects.create(name="Группа")
    return Competency.objects.create(name="К", group=group, scale=scale)


def _fill_score(assignment: ReviewerAssignment, competency: Competency, score: int) -> None:
    """Заполнить оценку и отметить назначение завершённым."""
    AssessmentResponse.objects.create(assignment=assignment, competency=competency, score=score)
    mark_assignment_completed(assignment)


@pytest.mark.django_db
def test_aggregate_has_no_raw_scores() -> None:
    """Агрегат НЕ содержит сырых оценок оценщиков (только средние)."""
    # Подготовка: цикл, участник, 3 подчинённых-оценщика.
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
    subs = [_make_employee(f"S{i}", f"s{i}@corp.local") for i in range(3)]
    a_subs = [
        ReviewerAssignment.objects.create(
            cycle=cycle,
            participant=participant,
            reviewer=s,
            group=ReviewerAssignment.Group.SUBORDINATE.value,
        )
        for s in subs
    ]
    _fill_score(a_mgr, competency, 5)
    for a in a_subs:
        _fill_score(a, competency, 4)

    aggregate = aggregate_cycle(cycle)

    # В результате нет ссылок на конкретные assignment_id/score отдельных оценщиков.
    assert all(g.mean_score > 0 for g in aggregate.groups if g.participants_count > 0)
    # Никаких сырых объектов AssessmentResponse в агрегате нет (по типу данных).
    for g in aggregate.groups:
        assert not hasattr(g, "responses")
        assert not hasattr(g, "scores")


@pytest.mark.django_db
def test_group_below_threshold_is_hidden() -> None:
    """Группа с числом оценщиков ниже порога скрыта (SPEC §6.3)."""
    cycle = AssessmentCycle.objects.create(name="Цикл", anonymity_threshold=3)
    emp = _make_employee("E1", "e1@corp.local")
    competency = _make_competency()
    participant = Participant.objects.create(cycle=cycle, employee=emp)

    # Менеджер (обязательно, группа из 1 — но manager не скрывается).
    manager = _make_employee("M1", "m1@corp.local")
    a_mgr = ReviewerAssignment.objects.create(
        cycle=cycle,
        participant=participant,
        reviewer=manager,
        group=ReviewerAssignment.Group.MANAGER.value,
    )
    _fill_score(a_mgr, competency, 5)

    # Подчинённых только 2 — ниже порога 3 → должны быть скрыты.
    subs = [_make_employee(f"S{i}", f"s{i}@corp.local") for i in range(2)]
    for s in subs:
        a = ReviewerAssignment.objects.create(
            cycle=cycle,
            participant=participant,
            reviewer=s,
            group=ReviewerAssignment.Group.SUBORDINATE.value,
        )
        _fill_score(a, competency, 3)

    aggregate = aggregate_cycle(cycle)

    sub_group = next(g for g in aggregate.groups if g.group == "subordinate")
    assert sub_group.hidden_by_threshold is True
    assert sub_group.participants_count == 2


@pytest.mark.django_db
def test_group_above_threshold_is_shown() -> None:
    """Группа с числом оценщиков ≥ порога — отображается."""
    cycle = AssessmentCycle.objects.create(name="Цикл", anonymity_threshold=3)
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
    _fill_score(a_mgr, competency, 5)

    # 3 подчинённых — ровно порог.
    for i in range(3):
        s = _make_employee(f"S{i}", f"s{i}@corp.local")
        a = ReviewerAssignment.objects.create(
            cycle=cycle,
            participant=participant,
            reviewer=s,
            group=ReviewerAssignment.Group.SUBORDINATE.value,
        )
        _fill_score(a, competency, 4)

    aggregate = aggregate_cycle(cycle)

    sub_group = next(g for g in aggregate.groups if g.group == "subordinate")
    assert sub_group.hidden_by_threshold is False
    assert sub_group.mean_score == 4.0


@pytest.mark.django_db
def test_raw_responses_not_exposed_via_aggregate() -> None:
    """Из агрегата невозможно восстановить, кто именно как оценил."""
    cycle = AssessmentCycle.objects.create(name="Цикл", anonymity_threshold=3)
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
    _fill_score(a_mgr, competency, 5)

    subs = [_make_employee(f"S{i}", f"s{i}@corp.local") for i in range(4)]
    for s in subs:
        a = ReviewerAssignment.objects.create(
            cycle=cycle,
            participant=participant,
            reviewer=s,
            group=ReviewerAssignment.Group.SUBORDINATE.value,
        )
        # Разные оценки, чтобы проверить, что среднее не деанонимизирует.
        _fill_score(a, competency, [2, 3, 4, 5][subs.index(s)])

    aggregate = aggregate_cycle(cycle)
    sub_group = next(g for g in aggregate.groups if g.group == "subordinate")

    # Доступно только среднее и счётчик; отдельные оценки (2,3,4,5) невосстановимы.
    assert sub_group.mean_score == 3.5
    assert sub_group.participants_count == 4
    # Нет полей с отдельными оценками или идентификаторами оценщиков.
    assert "reviewer" not in sub_group.__dict__
    assert "assignment" not in sub_group.__dict__
