"""Политика хранения данных оценок (SPEC §12.6, issue #43)."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any

import pytest
from django.utils import timezone

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
from apps.users.models import User


def _make_closed_cycle(*, name: str) -> tuple[AssessmentCycle, AssessmentResponse]:
    """Создать закрытый цикл с одной оценкой и текстовым комментарием."""
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
        status=AssessmentCycle.Status.CLOSED,
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


@pytest.mark.django_db
def test_retention_archives_aggregate_and_deletes_only_cycles_older_than_boundary() -> None:
    """Старое сырьё удаляется, а обезличенный агрегат остаётся доступен."""
    now = datetime(2031, 8, 31, 12, tzinfo=timezone.get_current_timezone())
    cutoff = now.replace(year=2026)
    expired_cycle, expired_response = _make_closed_cycle(name="expired")
    boundary_cycle, boundary_response = _make_closed_cycle(name="boundary")
    AssessmentCycle.objects.filter(pk=expired_cycle.pk).update(
        updated_at=cutoff - timedelta(microseconds=1)
    )
    AssessmentCycle.objects.filter(pk=boundary_cycle.pk).update(updated_at=cutoff)
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
    assert not AssessmentResponse.objects.filter(pk=expired_response.pk).exists()
    assert AssessmentResponse.objects.filter(pk=boundary_response.pk).exists()

    archive = AssessmentAggregateArchive.objects.get(cycle=expired_cycle)
    assert archive.payload == expected_archive
    assert "reviewer" not in str(archive.payload)
    assert "comment" not in str(archive.payload)
    assert aggregate_cycle(expired_cycle).groups[0].mean_score == 5.0

    audit = AuditLogEntry.objects.get(action="assessment.retention.run")
    assert audit.actor is None
    assert audit.details == {
        "aggregate_mode": "archive",
        "archives_created": 1,
        "comments_deleted": 1,
        "cycles_processed": 1,
        "responses_deleted": 1,
    }
    assert "Сильный результат" not in str(audit.details)


@pytest.mark.django_db
def test_retention_delete_mode_is_idempotent() -> None:
    """Режим delete не сохраняет агрегат, повторный запуск ничего не удаляет."""
    now = datetime(2031, 8, 31, 12, tzinfo=timezone.get_current_timezone())
    cycle, _ = _make_closed_cycle(name="delete")
    AssessmentCycle.objects.filter(pk=cycle.pk).update(
        updated_at=now.replace(year=2026) - timedelta(seconds=1)
    )

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
    assert second.cycles_processed == 0
    assert second.responses_deleted == 0
    assert second.comments_deleted == 0
    assert not AssessmentAggregateArchive.objects.filter(cycle=cycle).exists()


@pytest.mark.django_db
def test_retention_task_uses_deployment_settings(settings: Any) -> None:
    """Celery-задача получает срок и судьбу агрегатов из настроек deployment."""
    settings.DATA_RETENTION_YEARS = 7
    settings.ASSESSMENT_AGGREGATE_RETENTION_MODE = "delete"
    cycle, _ = _make_closed_cycle(name="task")
    AssessmentCycle.objects.filter(pk=cycle.pk).update(
        updated_at=timezone.now().replace(year=timezone.now().year - 8)
    )

    result = run_assessment_retention()

    assert result == {
        "aggregate_mode": "delete",
        "archives_created": 0,
        "comments_deleted": 1,
        "cycles_processed": 1,
        "responses_deleted": 1,
    }


@pytest.mark.django_db
def test_retention_rejects_unknown_aggregate_mode_without_deleting_data() -> None:
    """Ошибка конфигурации останавливает очистку до любых удалений."""
    cycle, response = _make_closed_cycle(name="invalid")
    AssessmentCycle.objects.filter(pk=cycle.pk).update(
        updated_at=timezone.now().replace(year=timezone.now().year - 6)
    )

    with pytest.raises(ValueError, match="aggregate_mode"):
        apply_assessment_retention(
            now=timezone.now(),
            retention_years=5,
            aggregate_mode="unknown",
        )

    assert AssessmentResponse.objects.filter(pk=response.pk).exists()
