"""Политика хранения данных оценок (SPEC §12.6, issue #43)."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.assessment.models import (
    AssessmentAggregateArchive,
    AssessmentComment,
    AssessmentCycle,
    AssessmentResponse,
    Participant,
    ReviewerAssignment,
)
from apps.assessment.services import aggregate_cycle, apply_assessment_retention
from apps.assessment.tasks import run_assessment_retention
from apps.audit.models import AuditLogEntry
from apps.competencies.models import Competency, CompetencyGroup, Scale
from apps.orgstructure.models import Department, Employee, Position
from apps.users.models import Role, User


def _make_cycle(
    *, name: str, status_value: str = AssessmentCycle.Status.CLOSED
) -> tuple[AssessmentCycle, AssessmentResponse]:
    """Создать цикл с одной оценкой и текстовым комментарием."""
    department = Department.objects.create(code_1c=f"D-{name}", name=f"Отдел {name}")
    position = Position.objects.create(code_1c=f"P-{name}", name=f"Должность {name}")
    employee_user = User.objects.create_user(
        email=f"employee-{name}@corp.local", password="Strong-Pwd-1"
    )
    manager_user = User.objects.create_user(
        email=f"manager-{name}@corp.local", password="Strong-Pwd-1"
    )
    employee = Employee.objects.create(
        code_1c=f"E-{name}",
        user=employee_user,
        last_name="Сотрудник",
        first_name=name,
        department=department,
        position=position,
    )
    manager = Employee.objects.create(
        code_1c=f"M-{name}",
        user=manager_user,
        last_name="Руководитель",
        first_name=name,
        department=department,
        position=position,
    )
    scale = Scale.objects.create(name=f"Шкала {name}", min_value=1, max_value=5)
    group = CompetencyGroup.objects.create(name=f"Группа {name}")
    competency = Competency.objects.create(name=f"Компетенция {name}", group=group, scale=scale)
    cycle = AssessmentCycle.objects.create(
        name=name,
        status=status_value,
        anonymity_threshold=3,
    )
    participant = Participant.objects.create(cycle=cycle, employee=employee)
    assignment = ReviewerAssignment.objects.create(
        cycle=cycle,
        participant=participant,
        reviewer=manager,
        group=ReviewerAssignment.Group.MANAGER,
        completed=True,
        completed_at=timezone.now(),
    )
    response = AssessmentResponse.objects.create(
        assignment=assignment,
        competency=competency,
        score=5,
    )
    AssessmentComment.objects.create(
        assignment=assignment,
        text="Сильный результат, содержащий чувствительные данные",
        is_general=True,
    )
    return cycle, response


def _set_raw_created_at(cycle: AssessmentCycle, value: datetime) -> None:
    """Установить детерминированное время сырья для проверки границы срока."""
    AssessmentResponse.objects.filter(assignment__cycle=cycle).update(created_at=value)
    AssessmentComment.objects.filter(assignment__cycle=cycle).update(created_at=value)


@pytest.mark.django_db
def test_retention_archives_aggregate_and_deletes_only_cycles_older_than_boundary() -> None:
    """Старое сырьё удаляется, а обезличенный агрегат остаётся доступен."""
    now = datetime(2031, 8, 31, 12, tzinfo=timezone.get_current_timezone())
    cutoff = now.replace(year=2026)
    expired_cycle, expired_response = _make_cycle(
        name="expired",
        status_value=AssessmentCycle.Status.IN_PROGRESS,
    )
    boundary_cycle, boundary_response = _make_cycle(name="boundary")
    _set_raw_created_at(expired_cycle, cutoff - timedelta(microseconds=1))
    _set_raw_created_at(boundary_cycle, cutoff)
    expected_archive = asdict(aggregate_cycle(expired_cycle))

    result = apply_assessment_retention(
        now=now,
        retention_years=5,
        aggregate_mode="archive",
    )

    assert result.cycles_processed == 1
    assert result.responses_deleted == 1
    assert result.comments_deleted == 1
    assert result.archives_created == 1
    assert result.archives_deleted == 0
    assert not AssessmentResponse.objects.filter(pk=expired_response.pk).exists()
    assert AssessmentResponse.objects.filter(pk=boundary_response.pk).exists()
    expired_cycle.refresh_from_db()
    assert expired_cycle.status == AssessmentCycle.Status.CLOSED

    archive = AssessmentAggregateArchive.objects.get(cycle=expired_cycle)
    assert archive.payload == expected_archive
    assert "reviewer" not in str(archive.payload)
    assert "comment" not in str(archive.payload)
    archived_group = aggregate_cycle(expired_cycle).groups[0]
    assert archived_group.hidden_by_threshold is True
    assert archived_group.mean_score == 0.0

    audit = AuditLogEntry.objects.get(action="assessment.retention.run")
    assert audit.actor is None
    assert audit.details == {
        "aggregate_mode": "archive",
        "archives_created": 1,
        "archives_deleted": 0,
        "comments_deleted": 1,
        "cycles_processed": 1,
        "responses_deleted": 1,
    }
    assert "Сильный результат" not in str(audit.details)


@pytest.mark.django_db
def test_retention_delete_mode_is_idempotent() -> None:
    """Режим delete не сохраняет агрегат, повторный запуск ничего не удаляет."""
    now = datetime(2031, 8, 31, 12, tzinfo=timezone.get_current_timezone())
    cycle, _ = _make_cycle(name="delete")
    _set_raw_created_at(cycle, now.replace(year=2026) - timedelta(seconds=1))

    first = apply_assessment_retention(
        now=now,
        retention_years=5,
        aggregate_mode="delete",
    )
    second = apply_assessment_retention(
        now=now,
        retention_years=5,
        aggregate_mode="delete",
    )

    assert first.cycles_processed == 1
    assert first.responses_deleted == 1
    assert first.comments_deleted == 1
    assert first.archives_created == 0
    assert first.archives_deleted == 0
    assert second.cycles_processed == 0
    assert second.responses_deleted == 0
    assert second.comments_deleted == 0
    assert second.archives_deleted == 0
    assert not AssessmentAggregateArchive.objects.filter(cycle=cycle).exists()


@pytest.mark.django_db
def test_retention_task_uses_deployment_settings(settings: Any) -> None:
    """Celery-задача получает срок и судьбу агрегатов из настроек deployment."""
    settings.DATA_RETENTION_YEARS = 7
    settings.ASSESSMENT_AGGREGATE_RETENTION_MODE = "delete"
    cycle, _ = _make_cycle(name="task")
    _set_raw_created_at(cycle, timezone.now().replace(year=timezone.now().year - 8))

    result = run_assessment_retention()

    assert result == {
        "aggregate_mode": "delete",
        "archives_created": 0,
        "archives_deleted": 0,
        "comments_deleted": 1,
        "cycles_processed": 1,
        "responses_deleted": 1,
    }


@pytest.mark.django_db
def test_retention_rejects_unknown_aggregate_mode_without_deleting_data() -> None:
    """Ошибка конфигурации останавливает очистку до любых удалений."""
    cycle, response = _make_cycle(name="invalid")
    _set_raw_created_at(cycle, timezone.now().replace(year=timezone.now().year - 6))

    with pytest.raises(ValueError, match="aggregate_mode"):
        apply_assessment_retention(
            now=timezone.now(),
            retention_years=5,
            aggregate_mode="unknown",
        )

    assert AssessmentResponse.objects.filter(pk=response.pk).exists()


@pytest.mark.django_db
def test_employee_cannot_access_archived_aggregate() -> None:
    """Архивный агрегат сохраняет те же ограничения доступа, что и живой."""
    cycle, _ = _make_cycle(name="permissions")
    _set_raw_created_at(cycle, timezone.now().replace(year=timezone.now().year - 6))
    apply_assessment_retention(
        now=timezone.now(),
        retention_years=5,
        aggregate_mode="archive",
    )
    user = User.objects.create_user(email="unauthorized@corp.local", password="Strong-Pwd-1")
    role = Role.objects.create(code=Role.Code.EMPLOYEE, name="Сотрудник")
    user.roles.add(role)
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get(f"/api/v1/assessment/cycles/{cycle.pk}/results/")

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_retention_archives_and_cleans_whole_cycle_when_first_raw_item_expires() -> None:
    """Снимок полон, а ни один сырой объект не хранится сверх срока."""
    now = timezone.now()
    cutoff = now.replace(year=now.year - 5)
    cycle, response = _make_cycle(name="mixed-age")
    comment = AssessmentComment.objects.get(assignment__cycle=cycle)
    AssessmentResponse.objects.filter(pk=response.pk).update(
        created_at=cutoff - timedelta(seconds=1)
    )
    AssessmentComment.objects.filter(pk=comment.pk).update(created_at=cutoff)

    result = apply_assessment_retention(
        now=now,
        retention_years=5,
        aggregate_mode="archive",
    )

    assert result.cycles_processed == 1
    assert result.responses_deleted == 1
    assert result.comments_deleted == 1
    assert not AssessmentResponse.objects.filter(pk=response.pk).exists()
    assert not AssessmentComment.objects.filter(pk=comment.pk).exists()
    assert AssessmentAggregateArchive.objects.filter(cycle=cycle).exists()
    cycle.refresh_from_db()
    assert cycle.status == AssessmentCycle.Status.CLOSED


@pytest.mark.django_db
def test_delete_mode_removes_previously_created_archive() -> None:
    """Смена deployment-политики на delete удаляет существующий snapshot."""
    now = timezone.now()
    cycle, _ = _make_cycle(name="archive-to-delete")
    _set_raw_created_at(cycle, now.replace(year=now.year - 6))
    apply_assessment_retention(
        now=now,
        retention_years=5,
        aggregate_mode="archive",
    )
    assert AssessmentAggregateArchive.objects.filter(cycle=cycle).exists()

    result = apply_assessment_retention(
        now=now,
        retention_years=5,
        aggregate_mode="delete",
    )

    assert result.cycles_processed == 0
    assert result.archives_deleted == 1
    assert not AssessmentAggregateArchive.objects.filter(cycle=cycle).exists()
