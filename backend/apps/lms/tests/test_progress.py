"""Тесты прогресса и сертификации курсов (Test-First, SPEC §7.4, issue #22).

Контракты:
- запись на курс (enrollment) создаётся;
- отметка урока пройденным увеличивает прогресс;
- прогресс корректно считается по урокам (% завершения);
- статус «пройдён» выставляется по критерию (≥ pass_threshold);
- пройденный курс попадает в портфолио.
"""

from __future__ import annotations

import pytest

from apps.lms.models import Course, Enrollment, Lesson, LessonProgress
from apps.lms.services import mark_lesson_completed, recalculate_progress
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


def _course_with_lessons(n: int = 4, *, pass_threshold: int = 80) -> tuple[Course, list[Lesson]]:
    """Создать курс с N уроками."""
    course = Course.objects.create(
        title="Курс", status=Course.Status.PUBLISHED.value, pass_threshold=pass_threshold
    )
    lessons = [
        Lesson.objects.create(
            course=course, title=f"Урок {i}", type=Lesson.Type.TEXT.value, order=i
        )
        for i in range(1, n + 1)
    ]
    return course, lessons


@pytest.mark.django_db
def test_enrollment_created_on_course_join() -> None:
    """Запись на курс создаётся со статусом not_started."""
    course, _ = _course_with_lessons(2)
    emp = _employee("E1", "e1@corp.local")

    enrollment = Enrollment.objects.create(course=course, employee=emp)

    assert enrollment.status == Enrollment.Status.NOT_STARTED.value
    assert enrollment.progress_percent == 0


@pytest.mark.django_db
def test_mark_lesson_completed_increases_progress() -> None:
    """Отметка урока пройденным увеличивает % завершения."""
    course, lessons = _course_with_lessons(4)
    emp = _employee("E1", "e1@corp.local")
    enrollment = Enrollment.objects.create(course=course, employee=emp)

    mark_lesson_completed(enrollment, lessons[0])

    assert enrollment.progress_percent == 25  # 1 из 4
    lp = LessonProgress.objects.get(enrollment=enrollment, lesson=lessons[0])
    assert lp.completed is True


@pytest.mark.django_db
def test_progress_calculated_by_lessons() -> None:
    """Прогресс = % пройденных уроков (SPEC §7.4)."""
    course, lessons = _course_with_lessons(4)
    emp = _employee("E1", "e1@corp.local")
    enrollment = Enrollment.objects.create(course=course, employee=emp)
    mark_lesson_completed(enrollment, lessons[0])
    mark_lesson_completed(enrollment, lessons[1])

    recalculate_progress(enrollment)

    assert enrollment.progress_percent == 50


@pytest.mark.django_db
def test_course_completed_when_threshold_met() -> None:
    """Статус «пройдён» при достижении порога (SPEC §7.4)."""
    course, lessons = _course_with_lessons(4, pass_threshold=75)
    emp = _employee("E1", "e1@corp.local")
    enrollment = Enrollment.objects.create(course=course, employee=emp)
    # 3 из 4 = 75% ≥ порога 75.
    for lesson in lessons[:3]:
        mark_lesson_completed(enrollment, lesson)

    recalculate_progress(enrollment)

    assert enrollment.status == Enrollment.Status.COMPLETED.value
    assert enrollment.completed_at is not None


@pytest.mark.django_db
def test_completed_course_recorded_to_portfolio() -> None:
    """Пройденный курс попадает в портфолио сотрудника (SPEC §7.4)."""
    from apps.portfolio.models import PortfolioEntry

    course, lessons = _course_with_lessons(2, pass_threshold=100)
    emp = _employee("E1", "e1@corp.local")
    enrollment = Enrollment.objects.create(course=course, employee=emp)
    for lesson in lessons:
        mark_lesson_completed(enrollment, lesson)

    recalculate_progress(enrollment)

    assert PortfolioEntry.objects.filter(employee=emp, title__contains=course.title).exists()
