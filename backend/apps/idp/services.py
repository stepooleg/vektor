"""Сервисы ИПР — автоподбор и жизненный цикл (SPEC §8.1, §8.3).

- ``generate_idp_from_zones``: создание ИПР из зон развития с подбором курсов
  по привязке к компетенциям (CourseCompetencyLink);
- ``add_manual_action``: ручная правка — добавить действие в цель;
- ``transition_plan``: конечный автомат статусов ИПР.
"""

from __future__ import annotations

from datetime import date

from django.db import transaction

from apps.assessment.models import (
    AssessmentCycle,
    AssessmentResponse,
    ExpectedLevel,
    Participant,
    ReviewerAssignment,
)
from apps.competencies.models import Competency
from apps.lms.models import Course, CourseCompetencyLink
from apps.orgstructure.models import Employee

from .matrix import DevelopmentZone
from .models import DevAction, DevelopmentPlan, DevGoal

# Допустимые переходы статусов ИПР (SPEC §8.3).
_PLAN_TRANSITIONS: dict[str, set[str]] = {
    DevelopmentPlan.Status.DRAFT.value: {DevelopmentPlan.Status.APPROVED.value},
    DevelopmentPlan.Status.APPROVED.value: {DevelopmentPlan.Status.IN_PROGRESS.value},
    DevelopmentPlan.Status.IN_PROGRESS.value: {DevelopmentPlan.Status.COMPLETED.value},
    DevelopmentPlan.Status.COMPLETED.value: set(),
}


@transaction.atomic
def generate_idp_from_zones(
    *,
    employee: Employee,
    zones: list[DevelopmentZone],
    source_cycle: AssessmentCycle | None = None,
) -> DevelopmentPlan:
    """Создать ИПР из зон развития с автоподбором курсов (SPEC §8.1).

    Для каждой зоны (компетенция ниже ожидаемого):
    - создаётся цель DevGoal;
    - подбираются курсы через CourseCompetencyLink → DevAction(type=course).
    """
    plan = DevelopmentPlan.objects.create(employee=employee)
    for zone in zones:
        competency = zone.competency
        if competency is None and zone.competency_id is not None:
            competency = Competency.objects.filter(id=zone.competency_id).first()
        if competency is None:
            continue
        goal = DevGoal.objects.create(
            plan=plan,
            competency=competency,
            title=f"Развитие: {competency.name}",
            target_level=zone.expected_level,
            source_cycle=source_cycle,
            source_current_level=zone.current_level if source_cycle else None,
        )
        # Автоподбор курсов по привязке к компетенции.
        for link in CourseCompetencyLink.objects.filter(competency=competency):
            DevAction.objects.create(
                goal=goal,
                type=DevAction.Type.COURSE.value,
                title=f"Курс: {link.course.title}",
                course=link.course,
            )
    return plan


def get_zones_from_assessment(
    *, employee: Employee, cycle: AssessmentCycle
) -> list[DevelopmentZone]:
    """Получить зоны из безопасных агрегатов участника цикла оценки.

    Оценки неанонимной группы используются только при достижении порога цикла.
    Самооценка не анонимна и может участвовать независимо от порога.
    """
    if cycle.status not in {
        AssessmentCycle.Status.AGGREGATED.value,
        AssessmentCycle.Status.CLOSED.value,
    }:
        return []
    participant = Participant.objects.filter(cycle=cycle, employee=employee).first()
    if participant is None:
        return []

    eligible_assignment_ids: list[int] = []
    for group in ReviewerAssignment.Group.values:
        assignment_ids = list(
            ReviewerAssignment.objects.filter(
                participant=participant,
                group=group,
                completed=True,
            ).values_list("id", flat=True)
        )
        if (
            group == ReviewerAssignment.Group.SELF.value
            or len(assignment_ids) >= cycle.anonymity_threshold
        ):
            eligible_assignment_ids.extend(assignment_ids)

    if not eligible_assignment_ids:
        return []
    expected_levels = ExpectedLevel.objects.filter(position=employee.position).select_related(
        "competency"
    )
    zones: list[DevelopmentZone] = []
    for expected in expected_levels:
        scores = list(
            AssessmentResponse.objects.filter(
                assignment_id__in=eligible_assignment_ids,
                competency=expected.competency,
            ).values_list("score", flat=True)
        )
        if not scores:
            continue
        current_level = round(sum(scores) / len(scores), 2)
        if current_level < expected.expected_level:
            zones.append(
                DevelopmentZone(
                    competency=expected.competency,
                    current_level=current_level,
                    expected_level=expected.expected_level,
                )
            )
    return zones


@transaction.atomic
def add_manual_action(  # noqa: PLR0913 — богатый API правки ИПР по SPEC §8.1
    *,
    goal: DevGoal,
    action_type: str,
    title: str,
    mentor: Employee | None = None,
    due_date: date | None = None,
    course: Course | None = None,
) -> DevAction:
    """Ручная правка: добавить действие в цель ИПР (SPEC §8.1)."""
    return DevAction.objects.create(
        goal=goal,
        type=action_type,
        title=title,
        mentor=mentor,
        due_date=due_date,
        course=course,
    )


def transition_plan(plan: DevelopmentPlan, target: DevelopmentPlan.Status) -> DevelopmentPlan:
    """Перевести ИПР в новый статус с проверкой перехода (SPEC §8.3).

    Raises:
        ValueError: если переход запрещён жизненным циклом.
    """
    current = plan.status
    if current == target.value:
        return plan
    allowed = _PLAN_TRANSITIONS.get(current, set())
    if target.value not in allowed:
        msg = f"Переход статуса ИПР «{current}» → «{target.value}» запрещён"
        raise ValueError(msg)
    plan.status = target.value
    plan.save(update_fields=["status", "updated_at"])
    return plan
