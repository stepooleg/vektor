"""Тесты моделей цикла оценки (Test-First, SPEC §5, issue #10).

Контракты:
- создание цикла с порогом анонимности (по умолчанию 3);
- участник привязан к циклу и сотруднику;
- назначение оценщика с группой (manager/peer/subordinate/self);
- сырой ответ AssessmentResponse хранит оценку по компетенции;
- уникальность оценщика на участника.
"""

from __future__ import annotations

import pytest
from django.db import IntegrityError

from apps.assessment.models import (
    AssessmentCycle,
    AssessmentResponse,
    Participant,
    ReviewerAssignment,
)
from apps.competencies.models import Competency, CompetencyGroup, Scale
from apps.orgstructure.models import Department, Employee, Position
from apps.users.models import User


def _make_employee(code: str, email: str) -> Employee:
    """Создать сотрудника для тестов."""
    dept = Department.objects.create(code_1c=f"D{code}", name=f"Отдел {code}")
    pos = Position.objects.create(code_1c=f"P{code}", name=f"Должность {code}")
    user = User.objects.create_user(email=email, password="Strong-Pwd-1")
    return Employee.objects.create(
        code_1c=code,
        user=user,
        last_name="Тестов",
        first_name=f"Сотрудник-{code}",
        department=dept,
        position=pos,
    )


def _make_competency() -> Competency:
    """Создать компетенцию со шкалой."""
    scale = Scale.objects.create(name="Шкала 1", min_value=1, max_value=5)
    group = CompetencyGroup.objects.create(name="Группа 1")
    return Competency.objects.create(name="Компетенция 1", group=group, scale=scale)


@pytest.mark.django_db
def test_cycle_default_anonymity_threshold_is_3() -> None:
    """Порог анонимности по умолчанию — 3 (SPEC §5.1.1)."""
    cycle = AssessmentCycle.objects.create(name="Цикл 2026")

    assert cycle.anonymity_threshold == 3
    assert cycle.status == AssessmentCycle.Status.CREATED.value


@pytest.mark.django_db
def test_participant_links_cycle_and_employee() -> None:
    """Участник связывает цикл и сотрудника."""
    cycle = AssessmentCycle.objects.create(name="Цикл")
    emp = _make_employee("E1", "e1@corp.local")
    participant = Participant.objects.create(cycle=cycle, employee=emp)

    assert participant.cycle_id == cycle.id
    assert participant.employee_id == emp.id


@pytest.mark.django_db
def test_reviewer_assignment_with_group() -> None:
    """Назначение оценщика фиксирует группу (manager/peer/subordinate/self)."""
    cycle = AssessmentCycle.objects.create(name="Цикл")
    emp = _make_employee("E1", "e1@corp.local")
    reviewer = _make_employee("E2", "e2@corp.local")
    participant = Participant.objects.create(cycle=cycle, employee=emp)

    assignment = ReviewerAssignment.objects.create(
        cycle=cycle,
        participant=participant,
        reviewer=reviewer,
        group=ReviewerAssignment.Group.MANAGER.value,
    )

    assert assignment.group == ReviewerAssignment.Group.MANAGER.value
    assert assignment.completed is False


@pytest.mark.django_db
def test_reviewer_unique_per_participant() -> None:
    """Один оценщик не назначается дважды на того же участника в цикле."""
    cycle = AssessmentCycle.objects.create(name="Цикл")
    emp = _make_employee("E1", "e1@corp.local")
    reviewer = _make_employee("E2", "e2@corp.local")
    participant = Participant.objects.create(cycle=cycle, employee=emp)
    ReviewerAssignment.objects.create(
        cycle=cycle,
        participant=participant,
        reviewer=reviewer,
        group=ReviewerAssignment.Group.PEER.value,
    )

    with pytest.raises(IntegrityError):
        ReviewerAssignment.objects.create(
            cycle=cycle,
            participant=participant,
            reviewer=reviewer,
            group=ReviewerAssignment.Group.SUBORDINATE.value,
        )


@pytest.mark.django_db
def test_raw_response_stores_score() -> None:
    """Сырой ответ хранит оценку по компетенции (SPEC §5.3)."""
    cycle = AssessmentCycle.objects.create(name="Цикл")
    emp = _make_employee("E1", "e1@corp.local")
    reviewer = _make_employee("E2", "e2@corp.local")
    competency = _make_competency()
    participant = Participant.objects.create(cycle=cycle, employee=emp)
    assignment = ReviewerAssignment.objects.create(
        cycle=cycle,
        participant=participant,
        reviewer=reviewer,
        group=ReviewerAssignment.Group.PEER.value,
    )

    response = AssessmentResponse.objects.create(
        assignment=assignment, competency=competency, score=4
    )

    assert response.score == 4
    assert response.competency_id == competency.id
