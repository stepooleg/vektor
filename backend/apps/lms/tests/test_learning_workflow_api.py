"""API-сценарии прохождения обучения (SPEC §7.2, §7.4, issue #68)."""

from __future__ import annotations

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.lms.models import AnswerOption, Course, Enrollment, Lesson, Question
from apps.orgstructure.models import Department, Employee, Position
from apps.users.models import Role, User


def _employee() -> tuple[Employee, APIClient]:
    """Создать сотрудника и аутентифицированный API-клиент."""
    department = Department.objects.create(code_1c="LMS-D", name="Обучение")
    position = Position.objects.create(code_1c="LMS-P", name="Слушатель")
    user = User.objects.create_user(email="student@corp.local", password="Strong-Pwd-1")
    role, _ = Role.objects.get_or_create(
        code=Role.Code.EMPLOYEE.value,
        defaults={"name": "Сотрудник"},
    )
    user.roles.add(role)
    employee = Employee.objects.create(
        code_1c="LMS-E",
        user=user,
        last_name="Иванов",
        first_name="Иван",
        department=department,
        position=position,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return employee, client


def _course() -> tuple[Course, Lesson, Lesson]:
    """Создать опубликованный курс с материалом и тестом."""
    course = Course.objects.create(
        title="Безопасная разработка",
        description="Практический курс",
        status=Course.Status.PUBLISHED.value,
        pass_threshold=100,
    )
    text_lesson = Lesson.objects.create(
        course=course,
        title="Введение",
        type=Lesson.Type.TEXT.value,
        content="Прочитайте правила.",
        order=1,
    )
    quiz = Lesson.objects.create(
        course=course,
        title="Проверка знаний",
        type=Lesson.Type.QUIZ.value,
        pass_score=100,
        order=2,
    )
    return course, text_lesson, quiz


@pytest.mark.django_db
def test_course_detail_exposes_program_without_correct_answers() -> None:
    """Страница курса получает программу, но не раскрывает верные ответы."""
    _, client = _employee()
    course, _, quiz = _course()
    question = Question.objects.create(
        lesson=quiz,
        text="Что нельзя хранить в репозитории?",
        type=Question.Type.SINGLE.value,
    )
    AnswerOption.objects.create(question=question, text="Секреты", is_correct=True)

    response = client.get(f"/api/v1/lms/courses/{course.id}/")

    assert response.status_code == status.HTTP_200_OK
    assert [lesson["title"] for lesson in response.data["lessons"]] == [
        "Введение",
        "Проверка знаний",
    ]
    option = response.data["lessons"][1]["questions"][0]["options"][0]
    assert "is_correct" not in option


@pytest.mark.django_db
def test_employee_enrolls_once_and_sees_course_in_my_learning() -> None:
    """Добровольная запись идемпотентна и появляется в личном кабинете."""
    employee, client = _employee()
    course, _, _ = _course()

    first = client.post(f"/api/v1/lms/courses/{course.id}/enroll/")
    second = client.post(f"/api/v1/lms/courses/{course.id}/enroll/")
    my_courses = client.get("/api/v1/lms/courses/my/")

    assert first.status_code == status.HTTP_201_CREATED
    assert second.status_code == status.HTTP_200_OK
    assert Enrollment.objects.filter(employee=employee, course=course).count() == 1
    assert my_courses.data[0]["course"]["title"] == course.title
    assert my_courses.data[0]["progress_percent"] == 0


@pytest.mark.django_db
def test_employee_completes_text_lesson_and_course_progress_changes() -> None:
    """Завершение материала обновляет личный прогресс."""
    _, client = _employee()
    course, text_lesson, _ = _course()
    client.post(f"/api/v1/lms/courses/{course.id}/enroll/")

    response = client.post(f"/api/v1/lms/courses/{course.id}/lessons/{text_lesson.id}/complete/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["progress_percent"] == 50
    assert response.data["status"] == Enrollment.Status.IN_PROGRESS.value


@pytest.mark.django_db
def test_passed_quiz_completes_course_and_issues_certificate() -> None:
    """Успешный тест завершает курс и выдаёт статус-сертификат."""
    _, client = _employee()
    course, text_lesson, quiz = _course()
    question = Question.objects.create(
        lesson=quiz,
        text="Выберите безопасный вариант",
        type=Question.Type.SINGLE.value,
    )
    correct = AnswerOption.objects.create(
        question=question, text="Использовать env", is_correct=True
    )
    AnswerOption.objects.create(question=question, text="Коммитить пароль", is_correct=False)
    client.post(f"/api/v1/lms/courses/{course.id}/enroll/")
    client.post(f"/api/v1/lms/courses/{course.id}/lessons/{text_lesson.id}/complete/")

    response = client.post(
        f"/api/v1/lms/courses/{course.id}/lessons/{quiz.id}/submit-quiz/",
        {"answers": {str(question.id): [correct.id]}},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["result"] == {"percent": 100, "passed": True}
    assert response.data["enrollment"]["status"] == Enrollment.Status.COMPLETED.value
    assert response.data["enrollment"]["certificate"]["course_title"] == course.title


@pytest.mark.django_db
def test_cannot_complete_lesson_without_enrollment() -> None:
    """Нельзя менять прогресс курса без записи на него."""
    _, client = _employee()
    course, text_lesson, _ = _course()

    response = client.post(f"/api/v1/lms/courses/{course.id}/lessons/{text_lesson.id}/complete/")

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_quiz_attempt_limit_is_enforced() -> None:
    """После исчерпания попыток повторная отправка блокируется."""
    _, client = _employee()
    course, _, quiz = _course()
    quiz.max_attempts = 1
    quiz.save(update_fields=["max_attempts"])
    question = Question.objects.create(
        lesson=quiz,
        text="Выберите ответ",
        type=Question.Type.SINGLE.value,
    )
    AnswerOption.objects.create(question=question, text="Верно", is_correct=True)
    wrong = AnswerOption.objects.create(question=question, text="Неверно", is_correct=False)
    client.post(f"/api/v1/lms/courses/{course.id}/enroll/")
    url = f"/api/v1/lms/courses/{course.id}/lessons/{quiz.id}/submit-quiz/"

    first = client.post(url, {"answers": {str(question.id): [wrong.id]}}, format="json")
    second = client.post(url, {"answers": {str(question.id): [wrong.id]}}, format="json")

    assert first.status_code == status.HTTP_200_OK
    assert first.data["enrollment"]["lesson_progresses"][0]["attempts_used"] == 1
    assert second.status_code == status.HTTP_400_BAD_REQUEST
    assert "попыт" in str(second.data).lower()
