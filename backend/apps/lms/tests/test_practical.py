"""Тесты практических заданий с проверкой куратором (Test-First, SPEC §7.2, issue #21).

Контракты:
- сотрудник отправляет ответ (submission создаётся, status=submitted);
- куратор видит очередь на проверку;
- оценка и комментарий сохраняются, submission → reviewed;
- сотрудник получает уведомление о результате;
- только назначенный куратор (или Методолог/HR) проверяет.
"""

from __future__ import annotations

import pytest
from django.core import mail

from apps.lms.models import Course, Lesson, PracticalTask, Submission
from apps.lms.services import (
    ReviewNotAllowed,
    get_review_queue,
    review_submission,
    submit_practical_task,
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


def _task(*, reviewer: Employee | None = None) -> PracticalTask:
    """Создать практическое задание."""
    course = Course.objects.create(title="Курс")
    lesson = Lesson.objects.create(course=course, title="Урок", type=Lesson.Type.TEXT.value)
    return PracticalTask.objects.create(
        lesson=lesson,
        title="Задание",
        description="Сделайте X",
        reviewer=reviewer,
    )


@pytest.mark.django_db
def test_employee_submits_answer() -> None:
    """Сотрудник отправляет ответ → submission создана со статусом submitted."""
    task = _task()
    emp = _employee("E1", "e1@corp.local")

    submission = submit_practical_task(task=task, employee=emp, answer_text="Мой ответ")

    assert submission.status == Submission.Status.SUBMITTED.value
    assert submission.answer_text == "Мой ответ"


@pytest.mark.django_db
def test_review_queue_shows_submitted() -> None:
    """Куратор видит очередь на проверку (статус submitted/in_review)."""
    reviewer = _employee("RV", "rv@corp.local")
    task = _task(reviewer=reviewer)
    emp = _employee("E1", "e1@corp.local")
    submit_practical_task(task=task, employee=emp, answer_text="Ответ")

    queue = get_review_queue(reviewer)

    assert queue.count() == 1
    first = queue.first()
    assert first is not None
    assert first.task_id == task.id


@pytest.mark.django_db
def test_review_saves_result_and_marks_reviewed() -> None:
    """Оценка и комментарий сохраняются, submission → reviewed."""
    reviewer = _employee("RV", "rv@corp.local")
    task = _task(reviewer=reviewer)
    emp = _employee("E1", "e1@corp.local")
    submission = submit_practical_task(task=task, employee=emp, answer_text="Ответ")

    review_submission(submission, reviewer=reviewer, passed=True, comment="Хорошая работа")

    submission.refresh_from_db()
    assert submission.status == Submission.Status.REVIEWED.value
    assert submission.review.passed is True
    assert submission.review.comment == "Хорошая работа"


@pytest.mark.django_db
def test_review_sends_notification_to_employee() -> None:
    """Сотрудник получает уведомление о результате (SPEC §13.2)."""
    reviewer = _employee("RV", "rv@corp.local")
    task = _task(reviewer=reviewer)
    emp = _employee("E1", "e1@corp.local")
    submission = submit_practical_task(task=task, employee=emp, answer_text="Ответ")

    review_submission(submission, reviewer=reviewer, passed=True, comment="Ок")

    # Уведомление отправлено сотруднику.
    assert any("e1@corp.local" in m.to[0] for m in mail.outbox)


@pytest.mark.django_db
def test_only_assigned_reviewer_can_review() -> None:
    """Только назначенный куратор (или Методолог/HR) проверяет; чужой — отказ."""
    reviewer = _employee("RV", "rv@corp.local")
    task = _task(reviewer=reviewer)
    emp = _employee("E1", "e1@corp.local")
    other = _employee("O1", "o1@corp.local")  # не назначен
    submission = submit_practical_task(task=task, employee=emp, answer_text="Ответ")

    with pytest.raises(ReviewNotAllowed):
        review_submission(submission, reviewer=other, passed=True, comment="...")
