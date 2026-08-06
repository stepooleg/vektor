"""Тесты жизненного цикла цикла оценки (Test-First, SPEC §5.2, issue #10).

Контракты:
- переходы статусов соблюдают жизненный цикл (created→assigned→...→closed);
- нельзя пропустить этапы (например, in_progress → created);
- нельзя агрегировать цикл без обязательной группы «руководитель»;
- автоформирование оценщиков по оргструктуре (руководитель + подчинённые).
"""

from __future__ import annotations

import pytest

from apps.assessment.models import (
    AssessmentCycle,
    Participant,
    ReviewerAssignment,
)
from apps.assessment.services import (
    CycleTransitionError,
    auto_assign_reviewers,
    transition_cycle,
)
from apps.orgstructure.models import Department, Employee, Position
from apps.users.models import User


def _make_employee(code: str, email: str, *, manager: Employee | None = None) -> Employee:
    """Создать сотрудника (с возможным руководителем)."""
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
        manager=manager,
    )


@pytest.mark.django_db
def test_transition_follows_lifecycle() -> None:
    """Переходы идут по жизненному циклу (SPEC §5.2)."""
    cycle = AssessmentCycle.objects.create(name="Цикл")
    assert cycle.status == AssessmentCycle.Status.CREATED.value

    transition_cycle(cycle, AssessmentCycle.Status.ASSIGNED)
    assert cycle.status == AssessmentCycle.Status.ASSIGNED.value

    transition_cycle(cycle, AssessmentCycle.Status.IN_PROGRESS)
    assert cycle.status == AssessmentCycle.Status.IN_PROGRESS.value


@pytest.mark.django_db
def test_transition_rejects_skip() -> None:
    """Нельзя перепрыгнуть этап (created → in_progress запрещён)."""
    cycle = AssessmentCycle.objects.create(name="Цикл")

    with pytest.raises(CycleTransitionError):
        transition_cycle(cycle, AssessmentCycle.Status.IN_PROGRESS)


@pytest.mark.django_db
def test_transition_rejects_backward() -> Exception | None:
    """Нельзя вернуться назад (in_progress → created)."""
    cycle = AssessmentCycle.objects.create(
        name="Цикл", status=AssessmentCycle.Status.IN_PROGRESS.value
    )

    with pytest.raises(CycleTransitionError):
        transition_cycle(cycle, AssessmentCycle.Status.CREATED)
    return None


@pytest.mark.django_db
def test_auto_assign_reviewers_from_orgstructure() -> None:
    """Автоформирование: руководитель + подчинённые (SPEC §5.1.1)."""
    boss = _make_employee("BOSS", "boss@corp.local")
    emp = _make_employee("E1", "e1@corp.local", manager=boss)
    sub1 = _make_employee("S1", "s1@corp.local", manager=emp)
    sub2 = _make_employee("S2", "s2@corp.local", manager=emp)

    cycle = AssessmentCycle.objects.create(name="Цикл")
    participant = Participant.objects.create(cycle=cycle, employee=emp)

    auto_assign_reviewers(participant)

    groups = dict(
        ReviewerAssignment.objects.filter(participant=participant).values_list(
            "reviewer_id", "group"
        )
    )
    # Руководитель emp = boss → группа manager.
    assert groups.get(boss.id) == ReviewerAssignment.Group.MANAGER.value
    # Подчинённые → группа subordinate.
    assert groups.get(sub1.id) == ReviewerAssignment.Group.SUBORDINATE.value
    assert groups.get(sub2.id) == ReviewerAssignment.Group.SUBORDINATE.value


@pytest.mark.django_db
def test_aggregate_requires_manager_group() -> None:
    """Нельзя агрегировать цикл без обязательной группы «руководитель» (SPEC §5.1.1)."""
    cycle = AssessmentCycle.objects.create(
        name="Цикл", status=AssessmentCycle.Status.IN_PROGRESS.value
    )
    emp = _make_employee("E1", "e1@corp.local")
    participant = Participant.objects.create(cycle=cycle, employee=emp)
    # Нет назначений → нет менеджера.
    _ = participant

    from apps.assessment.services import aggregate_cycle

    with pytest.raises(CycleTransitionError, match="руководитель"):
        aggregate_cycle(cycle)
