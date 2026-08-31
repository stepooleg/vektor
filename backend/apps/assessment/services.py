"""Сервисы модуля оценки (SPEC §5).

- ``transition_cycle``: конечный автомат статусов цикла (SPEC §5.2);
- ``auto_assign_reviewers``: формирование оценщиков по оргструктуре (§5.1.1);
- ``aggregate_cycle``: агрегация результатов с учётом порога анонимности (§6.3).

Анонимность и агрегация — критичны для комплаенса 152-ФЗ (см. test_lifecycle,
test_anonymity). Сырые ответы НЕ возвращаются публично — только агрегаты.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, NotRequired, TypedDict, cast

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.competencies.models import CompetencyFramework
from apps.orgstructure.models import Employee
from apps.users.models import User

from .models import (
    AssessmentAggregateArchive,
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
class AssessmentRetentionResult:
    """Технические счётчики одного запуска политики хранения."""

    aggregate_mode: str
    cycles_processed: int = 0
    responses_deleted: int = 0
    comments_deleted: int = 0
    archives_created: int = 0
    archives_deleted: int = 0

    def as_dict(self) -> dict[str, int | str]:
        """Вернуть JSON-совместимый результат для Celery и мониторинга."""
        return {
            "aggregate_mode": self.aggregate_mode,
            "archives_created": self.archives_created,
            "archives_deleted": self.archives_deleted,
            "comments_deleted": self.comments_deleted,
            "cycles_processed": self.cycles_processed,
            "responses_deleted": self.responses_deleted,
        }


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
    archive = AssessmentAggregateArchive.objects.filter(cycle=cycle).first()
    if archive is not None:
        return _deserialize_aggregate(archive.payload)

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


def _deserialize_aggregate(payload: object) -> CycleAggregate:
    """Восстановить публичный агрегат из созданного системой снимка."""
    data = cast(dict[str, object], payload)
    groups_data = cast(list[dict[str, object]], data["groups"])
    return CycleAggregate(
        cycle_id=int(cast(int, data["cycle_id"])),
        groups=[
            GroupAggregate(
                group=str(item["group"]),
                participants_count=int(cast(int, item["participants_count"])),
                mean_score=float(cast(float, item["mean_score"])),
                hidden_by_threshold=bool(item["hidden_by_threshold"]),
            )
            for item in groups_data
        ],
    )


def _subtract_years(value: datetime, years: int) -> datetime:
    """Вычесть календарные годы, корректно обработав 29 февраля."""
    try:
        return value.replace(year=value.year - years)
    except ValueError:
        return value.replace(year=value.year - years, day=28)


@transaction.atomic
def apply_assessment_retention(
    *,
    now: datetime,
    retention_years: int,
    aggregate_mode: str,
) -> AssessmentRetentionResult:
    """Удалить сырьё закрытых циклов старше срока и обработать агрегаты.

    Граница считается от неизменяемого ``created_at`` сырья. Когда истекает
    первый объект цикла, снимок строится по полному набору, всё сырьё цикла
    удаляется, а цикл закрывается. Поэтому ни один ответ не хранится сверх
    срока, а архив не становится частичным. Операция идемпотентна.
    """
    if retention_years <= 0:
        msg = "retention_years должен быть положительным"
        raise ValueError(msg)
    if aggregate_mode not in {"archive", "delete"}:
        msg = "aggregate_mode должен быть archive или delete"
        raise ValueError(msg)

    cutoff = _subtract_years(now, retention_years)
    expired_response_cycles = AssessmentResponse.objects.filter(created_at__lt=cutoff).values_list(
        "assignment__cycle_id", flat=True
    )
    expired_comment_cycles = AssessmentComment.objects.filter(created_at__lt=cutoff).values_list(
        "assignment__cycle_id", flat=True
    )
    cycle_ids = set(expired_response_cycles).union(expired_comment_cycles)
    cycles = list(
        AssessmentCycle.objects.select_for_update().filter(id__in=cycle_ids).order_by("id")
    )

    archives_deleted = 0
    if aggregate_mode == "delete":
        archive_query = AssessmentAggregateArchive.objects.all()
        archives_deleted = archive_query.count()
        archive_query.delete()

    responses_deleted = 0
    comments_deleted = 0
    archives_created = 0
    cycles_processed = 0
    for cycle in cycles:
        if aggregate_mode == "archive":
            aggregate = aggregate_cycle(cycle)
            _, created = AssessmentAggregateArchive.objects.get_or_create(
                cycle=cycle,
                defaults={"payload": asdict(aggregate)},
            )
            archives_created += int(created)

        response_query = AssessmentResponse.objects.filter(assignment__cycle=cycle)
        comment_query = AssessmentComment.objects.filter(assignment__cycle=cycle)
        responses_deleted += response_query.count()
        comments_deleted += comment_query.count()
        response_query.delete()
        comment_query.delete()
        if cycle.status != AssessmentCycle.Status.CLOSED:
            cycle.status = AssessmentCycle.Status.CLOSED
            cycle.save(update_fields=["status", "updated_at"])
        cycles_processed += 1

    result = AssessmentRetentionResult(
        aggregate_mode=aggregate_mode,
        cycles_processed=cycles_processed,
        responses_deleted=responses_deleted,
        comments_deleted=comments_deleted,
        archives_created=archives_created,
        archives_deleted=archives_deleted,
    )
    from apps.audit.services import log_action

    log_action(
        actor=None,
        action="assessment.retention.run",
        target_type="assessment.retention",
        details=result.as_dict(),
    )
    return result


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

    hidden_by_threshold = (
        participants_count < threshold and group_code != ReviewerAssignment.Group.SELF.value
    )
    return GroupAggregate(
        group=group_code,
        participants_count=participants_count,
        mean_score=0.0 if hidden_by_threshold else round(mean_score, 2),
        hidden_by_threshold=hidden_by_threshold,
    )


def mark_assignment_completed(assignment: ReviewerAssignment) -> None:
    """Отметить назначение оценщика как заполненное (SPEC §5.2, шаг 4)."""
    assignment.completed = True
    assignment.completed_at = timezone.now()
    assignment.save(update_fields=["completed", "completed_at"])
