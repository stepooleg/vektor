"""Сервисы LMS — автопроверка тестов и перемешивание (SPEC §7.2).

- ``grade_quiz``: автопроверка ответов по single/multiple;
- ``check_attempt_allowed``: лимит попыток;
- ``shuffled_question_ids``: детерминированное перемешивание вопросов.

Сертификация — только статус «пройдён/не пройдён» (SPEC §7.4), без PDF.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .models import AnswerOption, Lesson, Question

if TYPE_CHECKING:
    from collections.abc import Sequence

    from django.db.models import QuerySet


@dataclass(frozen=True)
class GradeResult:
    """Результат автопроверки теста."""

    percent: int
    passed: bool
    correct_count: int
    total_count: int


def grade_quiz(lesson: Lesson, answers: dict[int, list[int]]) -> GradeResult:
    """Проверить ответы теста и вернуть процент правильных.

    ``answers``: {question_id: [selected_option_id, ...]}.
    Засчитывается вопрос, где множество выбранных options полностью совпадает
    с множеством правильных (для multiple) или единственный правильный (single).
    """
    questions: Sequence[Question] = list(lesson.questions.all())
    total = len(questions)
    if total == 0:
        return GradeResult(percent=0, passed=False, correct_count=0, total_count=0)

    correct_map: dict[int, set[int]] = {
        q.id: set(q.options.filter(is_correct=True).values_list("id", flat=True)) for q in questions
    }
    correct_count = 0
    for q in questions:
        selected = set(answers.get(q.id, []))
        if selected and selected == correct_map[q.id]:
            correct_count += 1

    percent = int(round(correct_count / total * 100))
    return GradeResult(
        percent=percent,
        passed=percent >= lesson.pass_score,
        correct_count=correct_count,
        total_count=total,
    )


def check_attempt_allowed(lesson: Lesson, *, attempts_used: int) -> bool:
    """Разрешена ли новая попытка (лимит max_attempts, SPEC §7.2).

    ``max_attempts == 0`` трактуется как «без лимита».
    """
    if lesson.max_attempts == 0:
        return True
    return attempts_used < lesson.max_attempts


def shuffled_question_ids(lesson: Lesson, *, seed: int) -> list[int]:
    """Детерминированно перемешанные ID вопросов урока (SPEC §7.2).

    Одинаковый ``seed`` → одинаковый порядок (воспроизводимость при реране).
    """
    rng = random.Random(seed)
    ids = list(lesson.questions.values_list("id", flat=True))
    rng.shuffle(ids)
    return ids


def correct_option_ids(question: Question) -> set[int]:
    """Множество ID правильных вариантов вопроса (для UI/диагностики)."""
    return set(
        AnswerOption.objects.filter(question=question, is_correct=True).values_list("id", flat=True)
    )


# ---------------------------------------------------------------------------
# Практические задания с проверкой куратором (SPEC §7.2, issue #21)
# ---------------------------------------------------------------------------
from apps.orgstructure.models import Employee  # noqa: E402
from apps.users.models import Role  # noqa: E402

from .models import PracticalTask, Submission, TaskReview  # noqa: E402


class ReviewNotAllowed(Exception):
    """Недостаточно прав для проверки задания."""


def submit_practical_task(
    *, task: PracticalTask, employee: Employee, answer_text: str
) -> Submission:
    """Сотрудник отправляет ответ на задание (SPEC §7.2).

    Идемпотентно по (task, employee): обновляет текст, переводит в submitted.
    """
    submission, _ = Submission.objects.update_or_create(
        task=task,
        employee=employee,
        defaults={
            "answer_text": answer_text,
            "status": Submission.Status.SUBMITTED.value,
            "reviewed_at": None,
        },
    )
    return submission


def get_review_queue(reviewer: Employee) -> QuerySet[Submission]:
    """Очередь заданий на проверку для куратора (submitted/in_review).

    Методолог/HR видят все непроверенные; назначенный куратор — свои.
    """
    qs = Submission.objects.filter(
        status__in=[
            Submission.Status.SUBMITTED.value,
            Submission.Status.IN_REVIEW.value,
        ]
    )
    user = reviewer.user
    if user.has_any_role(Role.Code.METHODOLOGIST.value, Role.Code.HR.value):
        return qs
    return qs.filter(task__reviewer=reviewer)


def _can_review(reviewer: Employee, submission: Submission) -> bool:
    """Может ли сотрудник проверять эту submission (SPEC §7.2)."""
    user = reviewer.user
    if user.has_any_role(Role.Code.METHODOLOGIST.value, Role.Code.HR.value):
        return True
    return submission.task.reviewer_id == reviewer.id


def review_submission(
    submission: Submission,
    *,
    reviewer: Employee,
    passed: bool,
    comment: str = "",
    score: int | None = None,
) -> TaskReview:
    """Куратор проверяет ответ: оценка + комментарий → reviewed (SPEC §7.2).

    Отправляет уведомление сотруднику о результате (SPEC §13.2).
    """
    if not _can_review(reviewer, submission):
        raise ReviewNotAllowed("Только назначенный куратор может проверять задание")

    from django.utils import timezone

    review = TaskReview.objects.create(
        submission=submission,
        reviewer=reviewer,
        passed=passed,
        comment=comment,
        score=score,
    )
    submission.status = Submission.Status.REVIEWED.value
    submission.reviewed_at = timezone.now()
    submission.save(update_fields=["status", "reviewed_at"])

    # Уведомление сотруднику о результате (SPEC §13.2).
    _notify_review_result(submission, passed)

    return review


def _notify_review_result(submission: Submission, passed: bool) -> None:
    """Отправить сотруднику уведомление о результате проверки."""
    from apps.notifications.services import dispatch_notification

    if submission.employee.user_id is None:
        return
    dispatch_notification(
        event="course.result",
        user=submission.employee.user,
        context={
            "course_name": submission.task.lesson.course.title,
            "result": "зачтено" if passed else "не зачтено",
        },
    )


# ---------------------------------------------------------------------------
# Прогресс и сертификация (SPEC §7.4, issue #22)
# ---------------------------------------------------------------------------
from .models import Enrollment, LessonProgress  # noqa: E402


def mark_lesson_completed(enrollment: Enrollment, lesson: Lesson) -> LessonProgress:
    """Отметить урок пройденным и пересчитать прогресс курса (SPEC §7.4)."""
    progress, _ = LessonProgress.objects.update_or_create(
        enrollment=enrollment,
        lesson=lesson,
        defaults={"completed": True},
    )
    recalculate_progress(enrollment)
    return progress


def recalculate_progress(enrollment: Enrollment) -> Enrollment:
    """Пересчитать % завершения и статус курса (SPEC §7.4).

    Прогресс = % пройденных уроков. При достижении pass_threshold — статус
    COMPLETED и запись в портфолио.
    """
    from django.utils import timezone

    total = enrollment.course.lessons.count()
    completed = enrollment.lesson_progresses.filter(completed=True).count()
    percent = int(round(completed / total * 100)) if total else 0
    enrollment.progress_percent = percent

    just_completed = False
    if (
        percent >= enrollment.course.pass_threshold
        and enrollment.status != Enrollment.Status.COMPLETED.value
    ):
        enrollment.status = Enrollment.Status.COMPLETED.value
        enrollment.completed_at = timezone.now()
        just_completed = True
    elif percent > 0 and enrollment.status == Enrollment.Status.NOT_STARTED.value:
        enrollment.status = Enrollment.Status.IN_PROGRESS.value

    enrollment.save(update_fields=["status", "progress_percent", "completed_at"])

    if just_completed:
        _record_course_to_portfolio(enrollment)
        from .certificate import issue_certificate

        issue_certificate(enrollment)

    return enrollment


def _record_course_to_portfolio(enrollment: Enrollment) -> None:
    """Записать пройденный курс в портфолио сотрудника (SPEC §7.4)."""
    from apps.portfolio.models import PortfolioEntry

    PortfolioEntry.objects.get_or_create(
        employee=enrollment.employee,
        type=PortfolioEntry.Type.COURSE_PASSED.value,
        title=f"Курс пройдён: {enrollment.course.title}",
        defaults={"description": enrollment.course.description},
    )
