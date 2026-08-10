"""Сервисы модуля оценки (SPEC §5).

- ``transition_cycle``: конечный автомат статусов цикла (SPEC §5.2);
- ``auto_assign_reviewers``: формирование оценщиков по оргструктуре (§5.1.1);
- ``aggregate_cycle``: агрегация результатов с учётом порога анонимности (§6.3).

Анонимность и агрегация — критичны для комплаенса 152-ФЗ (см. test_lifecycle,
test_anonymity). Сырые ответы НЕ возвращаются публично — только агрегаты.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, NotRequired, TypedDict

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.competencies.models import CompetencyFramework
from apps.orgstructure.models import Employee
from apps.users.models import User

from .models import (
    AssessmentComment,
    AssessmentCycle,
    AssessmentResponse,
    Participant,
    ReviewerAssignment,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from apps.competencies.models import Competency


class CycleTransitionError(ValueError):
    """Нарушение правил жизненного цикла цикла."""


def eligible_participants_for_user(user: User) -> QuerySet[Employee]:
    """Вернуть доступных участников без раскрытия чужой оргструктуры."""
    eligible = Employee.objects.filter(is_active=True, assessment_eligible=True)
    if user.has_any_role("hr"):
        return eligible
    manager = Employee.objects.filter(user=user).first()
    if manager is None or not user.has_any_role("manager"):
        return Employee.objects.none()
    subordinate_ids = manager.get_subordinates().values_list("id", flat=True)
    return eligible.filter(id__in=subordinate_ids)


@dataclass(frozen=True)
class CycleCreationData:
    """Проверенные поля создаваемого цикла."""

    name: str
    framework: CompetencyFramework | None = None
    anonymity_threshold: int = 3
    start_date: date | None = None
    deadline: date | None = None


class AssignmentResponseInput(TypedDict):
    """Проверенный ответ по одной компетенции."""

    competency_id: int
    score: int
    comment: NotRequired[str]


@transaction.atomic
def create_cycle_with_participants(
    *,
    data: CycleCreationData,
    creator: User,
    participant_ids: list[int],
) -> AssessmentCycle:
    """Создать цикл и атомарно сформировать назначения выбранным участникам."""
    allowed = eligible_participants_for_user(creator)
    participants = list(allowed.filter(id__in=participant_ids).select_related("manager"))
    if len(participants) != len(set(participant_ids)):
        msg = "Выбраны недоступные сотрудники или сотрудники, не участвующие в оценке."
        raise CycleTransitionError(msg)
    if any(employee.manager_id is None for employee in participants):
        msg = "Для каждого участника должен быть назначен непосредственный руководитель."
        raise CycleTransitionError(msg)

    cycle = AssessmentCycle.objects.create(
        name=data.name,
        framework=data.framework,
        anonymity_threshold=data.anonymity_threshold,
        start_date=data.start_date,
        deadline=data.deadline,
        created_by=creator,
    )
    for employee in participants:
        participant = Participant.objects.create(cycle=cycle, employee=employee)
        auto_assign_reviewers(participant)
    if participants:
        transition_cycle(cycle, AssessmentCycle.Status.ASSIGNED)
    return cycle


@transaction.atomic
def submit_assignment(
    assignment: ReviewerAssignment,
    *,
    responses: list[AssignmentResponseInput],
    general_comment: str,
) -> None:
    """Сохранить полный опросник один раз, не возвращая сырые ответы наружу."""
    if assignment.completed:
        msg = "Оценка уже отправлена."
        raise CycleTransitionError(msg)
    if assignment.cycle.status != AssessmentCycle.Status.IN_PROGRESS.value:
        msg = "Ответы принимаются только в активном цикле."
        raise CycleTransitionError(msg)
    framework = assignment.cycle.framework
    if framework is None:
        msg = "Для цикла не выбрана модель компетенций."
        raise CycleTransitionError(msg)

    competencies = {
        competency.id: competency
        for competency in framework.competencies.select_related("scale").all()
    }
    response_ids = [item["competency_id"] for item in responses]
    if len(response_ids) != len(set(response_ids)) or set(response_ids) != set(competencies):
        msg = "Нужно оценить каждую компетенцию ровно один раз."
        raise CycleTransitionError(msg)

    for item in responses:
        competency = competencies[item["competency_id"]]
        score = item["score"]
        if not competency.scale.contains(score):
            msg = f"Оценка компетенции «{competency.name}» вне допустимой шкалы."
            raise CycleTransitionError(msg)
        AssessmentResponse.objects.create(
            assignment=assignment,
            competency=competency,
            score=score,
        )
        comment = str(item.get("comment", "")).strip()
        if comment:
            AssessmentComment.objects.create(
                assignment=assignment,
                competency=competency,
                text=comment,
            )
    if general_comment.strip():
        AssessmentComment.objects.create(
            assignment=assignment,
            text=general_comment.strip(),
            is_general=True,
        )
    mark_assignment_completed(assignment)


# Допустимые переходы статусов (SPEC §5.2). Ключ — текущий статус,
# значение — множество разрешённых следующих статусов.
_TRANSITIONS: dict[str, set[str]] = {
    AssessmentCycle.Status.CREATED.value: {AssessmentCycle.Status.ASSIGNED.value},
    AssessmentCycle.Status.ASSIGNED.value: {AssessmentCycle.Status.IN_PROGRESS.value},
    AssessmentCycle.Status.IN_PROGRESS.value: {AssessmentCycle.Status.COLLECTING.value},
    AssessmentCycle.Status.COLLECTING.value: {AssessmentCycle.Status.AGGREGATED.value},
    AssessmentCycle.Status.AGGREGATED.value: {AssessmentCycle.Status.CLOSED.value},
    AssessmentCycle.Status.CLOSED.value: set(),
}


@transaction.atomic
def transition_cycle(cycle: AssessmentCycle, target: AssessmentCycle.Status) -> AssessmentCycle:
    """Перевести цикл в ``target`` с проверкой допустимости перехода.

    Raises:
        CycleTransitionError: если переход запрещён жизненным циклом.
    """
    current = cycle.status
    if current == target.value:
        return cycle  # идемпотентно
    allowed = _TRANSITIONS.get(current, set())
    if target.value not in allowed:
        msg = f"Переход статуса «{current}» → «{target.value}» запрещён"
        raise CycleTransitionError(msg)
    cycle.status = target.value
    cycle.save(update_fields=["status", "updated_at"])
    return cycle


@transaction.atomic
def auto_assign_reviewers(
    participant: Participant,
    *,
    include_self: bool = True,
) -> list[ReviewerAssignment]:
    """Сформировать список оценщиков автоматически по оргструктуре (SPEC §5.1.1).

    - ``manager`` — непосредственный руководитель участника;
    - ``subordinate`` — прямые подчинённые участника;
    - ``self`` — сам участник (самооценка, если ``include_self``).

    Коллеги (peers) не определяются автоматически однозначно (требуют выбора
    из сотрудников того же уровня) — назначаются вручную.
    """
    created: list[ReviewerAssignment | None] = []
    emp: Employee = participant.employee

    # Руководитель.
    manager = emp.manager
    if manager is not None:
        created.append(
            _get_or_create_assignment(participant, manager, ReviewerAssignment.Group.MANAGER.value)
        )

    # Подчинённые (прямые).
    for sub in emp.get_subordinates(direct_only=True):
        created.append(
            _get_or_create_assignment(participant, sub, ReviewerAssignment.Group.SUBORDINATE.value)
        )

    # Самооценка.
    if include_self:
        created.append(
            _get_or_create_assignment(participant, emp, ReviewerAssignment.Group.SELF.value)
        )

    return [c for c in created if c is not None]


def _get_or_create_assignment(
    participant: Participant,
    reviewer: Employee,
    group: str,
) -> ReviewerAssignment | None:
    """Создать назначение, если ещё нет (идемпотентно). Возвращает None если дубль."""
    assignment, created = ReviewerAssignment.objects.get_or_create(
        cycle=participant.cycle,
        participant=participant,
        reviewer=reviewer,
        defaults={"group": group},
    )
    return assignment if created else None


@dataclass(frozen=True)
class GroupAggregate:
    """Агрегат по группе оценщиков (без сырых данных)."""

    group: str
    participants_count: int  # число оценщиков, заполнивших оценку
    mean_score: float
    hidden_by_threshold: bool  # True, если группа скрыта из-за порога


@dataclass(frozen=True)
class CycleAggregate:
    """Агрегированный результат цикла (только агрегаты, без сырых ответов)."""

    cycle_id: int
    groups: list[GroupAggregate]


@dataclass(frozen=True)
class SelfVsOthersGap:
    """Разрыв между самооценкой и оценкой окружения (SPEC §5.1.2)."""

    self_score: float
    others_score: float

    @property
    def gap(self) -> float:
        """Положительный gap — сотрудник оценил себя выше окружения."""
        return round(self.self_score - self.others_score, 2)


def get_self_vs_others_gap(participant: Participant, competency: Competency) -> SelfVsOthersGap:
    """Рассчитать разрыв self vs others по компетенции (SPEC §5.1.2).

    ``others`` — все группы, кроме ``self``.
    Возвращает 0.0 для стороны, по которой нет заполненных оценок.
    """
    self_score = _mean_score_for_group(participant, "self", competency)
    others_score = _mean_others_score(participant, competency)
    return SelfVsOthersGap(self_score=self_score, others_score=others_score)


def _mean_score_for_group(participant: Participant, group: str, competency: Competency) -> float:
    """Среднее по конкретной группе для участника и компетенции."""
    scores = list(
        AssessmentResponse.objects.filter(
            assignment__participant=participant,
            assignment__group=group,
            assignment__completed=True,
            competency=competency,
        ).values_list("score", flat=True)
    )
    return round(sum(scores) / len(scores), 2) if scores else 0.0


def _mean_others_score(participant: Participant, competency: Competency) -> float:
    """Среднее по всем группам, кроме self, для участника и компетенции."""
    others_groups = (
        ReviewerAssignment.Group.MANAGER.value,
        ReviewerAssignment.Group.PEER.value,
        ReviewerAssignment.Group.SUBORDINATE.value,
    )
    scores = list(
        AssessmentResponse.objects.filter(
            assignment__participant=participant,
            assignment__group__in=others_groups,
            assignment__completed=True,
            competency=competency,
        ).values_list("score", flat=True)
    )
    return round(sum(scores) / len(scores), 2) if scores else 0.0


@transaction.atomic
def aggregate_cycle(cycle: AssessmentCycle) -> CycleAggregate:
    """Рассчитать агрегированные результаты цикла (SPEC §6.3, §5.1.1).

    Требования:
    - цикл должен иметь обязательную группу «руководитель» у участников;
    - сырые ответы НЕ возвращаются — только средние по группам;
    - группы ниже порога анонимности помечаются ``hidden_by_threshold``.
    """
    # Проверка обязательной группы «руководитель».
    has_manager = ReviewerAssignment.objects.filter(
        cycle=cycle, group=ReviewerAssignment.Group.MANAGER.value
    ).exists()
    if not has_manager:
        msg = "Цикл нельзя агрегировать: нет группы «руководитель»"
        raise CycleTransitionError(msg)

    threshold = cycle.anonymity_threshold
    groups: list[GroupAggregate] = []

    for group_code in (
        ReviewerAssignment.Group.MANAGER.value,
        ReviewerAssignment.Group.PEER.value,
        ReviewerAssignment.Group.SUBORDINATE.value,
        ReviewerAssignment.Group.SELF.value,
    ):
        groups.append(_aggregate_group(cycle, group_code, threshold))

    return CycleAggregate(cycle_id=cycle.id, groups=groups)


def _aggregate_group(cycle: AssessmentCycle, group_code: str, threshold: int) -> GroupAggregate:
    """Агрегат по одной группе оценщиков (среднее по всем заполненным оценкам)."""
    assignments: Iterable[ReviewerAssignment] = ReviewerAssignment.objects.filter(
        cycle=cycle, group=group_code
    )
    # Число оценщиков, заполнивших оценку (completed=True).
    completed_reviewers = {a.id for a in assignments if a.completed}
    participants_count = len(completed_reviewers)

    # Среднее по сырым ответам этих assignment'ов.
    scores = list(
        AssessmentResponse.objects.filter(assignment_id__in=completed_reviewers).values_list(
            "score", flat=True
        )
    )
    mean_score = sum(scores) / len(scores) if scores else 0.0

    return GroupAggregate(
        group=group_code,
        participants_count=participants_count,
        mean_score=round(mean_score, 2),
        hidden_by_threshold=participants_count < threshold
        and group_code != ReviewerAssignment.Group.SELF.value,
    )


def mark_assignment_completed(assignment: ReviewerAssignment) -> None:
    """Отметить назначение оценщика как заполненное (SPEC §5.2, шаг 4)."""
    assignment.completed = True
    assignment.completed_at = timezone.now()
    assignment.save(update_fields=["completed", "completed_at"])
