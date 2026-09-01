"""REST API практических заданий (SPEC §7.2, issue #86)."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import cast

import pytest
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import StreamingHttpResponse
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.lms.models import Course, Lesson, PracticalTask, Submission, TaskReview
from apps.lms.services import submit_practical_task
from apps.orgstructure.models import Department, Employee, Position
from apps.users.models import User


def _employee_client(code: str = "E1") -> tuple[Employee, APIClient]:
    """Создать сотрудника и аутентифицированный API client."""
    department = Department.objects.create(code_1c=f"D-{code}", name="Отдел")
    position = Position.objects.create(code_1c=f"P-{code}", name="Специалист")
    user = User.objects.create_user(email=f"{code.lower()}@example.test", password="Password-1")
    employee = Employee.objects.create(
        code_1c=code,
        user=user,
        last_name="Иванов",
        first_name="Иван",
        department=department,
        position=position,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return employee, client


def _task() -> PracticalTask:
    """Создать практическое задание курса."""
    course = Course.objects.create(title="Курс")
    lesson = Lesson.objects.create(course=course, title="Практика", type=Lesson.Type.TEXT.value)
    return PracticalTask.objects.create(lesson=lesson, title="Отчёт", description="Приложите ответ")


@pytest.mark.django_db
def test_employee_submits_text_and_file_through_api(tmp_path: Path) -> None:
    """Сотрудник отправляет multipart-ответ через публичный LMS API."""
    employee, client = _employee_client()
    task = _task()
    attachment = SimpleUploadedFile(
        "report.pdf",
        b"%PDF-1.4 test document",
        content_type="application/pdf",
    )

    with override_settings(MEDIA_ROOT=tmp_path):
        response = client.post(
            "/api/v1/lms/submissions/",
            {"task": task.id, "answer_text": "Готово", "attachment": attachment},
            format="multipart",
        )

    assert response.status_code == status.HTTP_201_CREATED
    submission = Submission.objects.get(task=task, employee=employee)
    assert submission.answer_text == "Готово"
    assert submission.attachment.name.endswith("report.pdf")
    assert response.data["attachment_name"] == "report.pdf"
    assert "attachment" not in response.data


@pytest.mark.django_db
def test_empty_practical_submission_is_rejected() -> None:
    """Ответ должен содержать текст или файл."""
    _, client = _employee_client()
    task = _task()

    response = client.post(
        "/api/v1/lms/submissions/",
        {"task": task.id, "answer_text": "   "},
        format="multipart",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "non_field_errors" in response.data


@pytest.mark.django_db
@override_settings(LMS_SUBMISSION_MAX_FILE_SIZE=10)
def test_oversized_practical_attachment_is_rejected() -> None:
    """Размер вложения ограничивается deployment-настройкой."""
    _, client = _employee_client()
    task = _task()
    attachment = SimpleUploadedFile("answer.txt", b"12345678901", content_type="text/plain")

    response = client.post(
        "/api/v1/lms/submissions/",
        {"task": task.id, "attachment": attachment},
        format="multipart",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "attachment" in response.data


@pytest.mark.django_db
def test_unsafe_practical_attachment_type_is_rejected() -> None:
    """Исполняемые вложения не принимаются как ответы."""
    _, client = _employee_client()
    task = _task()
    attachment = SimpleUploadedFile(
        "payload.exe",
        b"MZ",
        content_type="application/x-msdownload",
    )

    response = client.post(
        "/api/v1/lms/submissions/",
        {"task": task.id, "attachment": attachment},
        format="multipart",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "attachment" in response.data


@pytest.mark.django_db
def test_executable_extension_cannot_spoof_safe_mime_type() -> None:
    """Проверка расширения не позволяет обойти allowlist подменой MIME."""
    _, client = _employee_client()
    task = _task()
    attachment = SimpleUploadedFile("payload.exe", b"MZ", content_type="application/pdf")

    response = client.post(
        "/api/v1/lms/submissions/",
        {"task": task.id, "attachment": attachment},
        format="multipart",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "attachment" in response.data


@pytest.mark.django_db
def test_employee_lists_only_own_practical_submissions() -> None:
    """Сотруднику не раскрываются ответы коллег."""
    employee, client = _employee_client("E1")
    colleague, _ = _employee_client("E2")
    task = _task()
    own = submit_practical_task(task=task, employee=employee, answer_text="Мой ответ")
    submit_practical_task(task=task, employee=colleague, answer_text="Чужой ответ")

    response = client.get("/api/v1/lms/submissions/")

    assert response.status_code == status.HTTP_200_OK
    assert [item["id"] for item in response.data["results"]] == [own.id]
    assert response.data["results"][0]["answer_text"] == "Мой ответ"


@pytest.mark.django_db
def test_assigned_reviewer_sees_only_permitted_queue() -> None:
    """Назначенный куратор видит свой ответ, посторонний — нет."""
    reviewer, reviewer_client = _employee_client("RV")
    _, other_client = _employee_client("OTHER")
    employee, _ = _employee_client("E1")
    task = _task()
    task.reviewer = reviewer
    task.save(update_fields=["reviewer"])
    submission = submit_practical_task(task=task, employee=employee, answer_text="Ответ")

    permitted = reviewer_client.get("/api/v1/lms/submissions/review-queue/")
    forbidden = other_client.get("/api/v1/lms/submissions/review-queue/")

    assert permitted.status_code == status.HTTP_200_OK
    assert [item["id"] for item in permitted.data["results"]] == [submission.id]
    assert permitted.data["results"][0]["employee_name"] == employee.full_name
    assert forbidden.status_code == status.HTTP_200_OK
    assert forbidden.data["results"] == []


@pytest.mark.django_db
def test_assigned_reviewer_reviews_submission_and_notifies_employee() -> None:
    """Назначенный куратор сохраняет результат, сотрудник получает уведомление."""
    reviewer, reviewer_client = _employee_client("RV")
    employee, _ = _employee_client("E1")
    task = _task()
    task.reviewer = reviewer
    task.save(update_fields=["reviewer"])
    submission = submit_practical_task(task=task, employee=employee, answer_text="Ответ")

    response = reviewer_client.post(
        f"/api/v1/lms/submissions/{submission.id}/review/",
        {"passed": True, "score": 5, "comment": "Отлично"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    submission.refresh_from_db()
    assert submission.status == Submission.Status.REVIEWED.value
    assert response.data == {"passed": True, "score": 5, "comment": "Отлично"}
    assert mail.outbox[-1].to == [employee.user.email]


@pytest.mark.django_db
def test_unassigned_reviewer_cannot_review_submission() -> None:
    """Посторонний сотрудник получает 403 и не меняет ответ."""
    reviewer, _ = _employee_client("RV")
    _, other_client = _employee_client("OTHER")
    employee, _ = _employee_client("E1")
    task = _task()
    task.reviewer = reviewer
    task.save(update_fields=["reviewer"])
    submission = submit_practical_task(task=task, employee=employee, answer_text="Ответ")

    response = other_client.post(
        f"/api/v1/lms/submissions/{submission.id}/review/",
        {"passed": True},
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    submission.refresh_from_db()
    assert submission.status == Submission.Status.SUBMITTED.value


@pytest.mark.django_db
def test_attachment_download_is_limited_to_owner_and_reviewer(tmp_path: Path) -> None:
    """Storage URL не публичен: файл получают только автор и куратор."""
    reviewer, reviewer_client = _employee_client("RV")
    _, other_client = _employee_client("OTHER")
    employee, employee_client = _employee_client("E1")
    task = _task()
    task.reviewer = reviewer
    task.save(update_fields=["reviewer"])
    attachment = SimpleUploadedFile("answer.txt", b"private answer", content_type="text/plain")

    with override_settings(MEDIA_ROOT=tmp_path):
        submission = submit_practical_task(
            task=task,
            employee=employee,
            answer_text="",
            attachment=attachment,
        )
        owner_response = employee_client.get(f"/api/v1/lms/submissions/{submission.id}/attachment/")
        reviewer_response = reviewer_client.get(
            f"/api/v1/lms/submissions/{submission.id}/attachment/"
        )
        forbidden_response = other_client.get(
            f"/api/v1/lms/submissions/{submission.id}/attachment/"
        )

        owner_stream = cast(StreamingHttpResponse, owner_response)
        reviewer_stream = cast(StreamingHttpResponse, reviewer_response)
        owner_content = cast(Iterable[bytes], owner_stream.streaming_content)
        reviewer_content = cast(Iterable[bytes], reviewer_stream.streaming_content)
        assert b"".join(owner_content) == b"private answer"
        assert b"".join(reviewer_content) == b"private answer"
    assert forbidden_response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_reviewed_submission_cannot_be_reviewed_twice() -> None:
    """Повторная проверка возвращает контролируемую ошибку и не создаёт 500."""
    reviewer, reviewer_client = _employee_client("RV")
    employee, _ = _employee_client("E1")
    task = _task()
    task.reviewer = reviewer
    task.save(update_fields=["reviewer"])
    submission = submit_practical_task(task=task, employee=employee, answer_text="Ответ")
    first = reviewer_client.post(
        f"/api/v1/lms/submissions/{submission.id}/review/",
        {"passed": True},
        format="json",
    )

    second = reviewer_client.post(
        f"/api/v1/lms/submissions/{submission.id}/review/",
        {"passed": False},
        format="json",
    )

    assert first.status_code == status.HTTP_200_OK
    assert second.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_employee_resubmission_reopens_review_workflow() -> None:
    """Новая версия ответа удаляет прежнюю оценку и возвращается в очередь."""
    reviewer, reviewer_client = _employee_client("RV")
    employee, employee_client = _employee_client("E1")
    task = _task()
    task.reviewer = reviewer
    task.save(update_fields=["reviewer"])
    submission = submit_practical_task(task=task, employee=employee, answer_text="Первая версия")
    reviewer_client.post(
        f"/api/v1/lms/submissions/{submission.id}/review/",
        {"passed": False, "comment": "Доработать"},
        format="json",
    )

    response = employee_client.post(
        "/api/v1/lms/submissions/",
        {"task": task.id, "answer_text": "Исправленная версия"},
        format="multipart",
    )

    assert response.status_code == status.HTTP_201_CREATED
    submission.refresh_from_db()
    assert submission.status == Submission.Status.SUBMITTED.value
    assert submission.answer_text == "Исправленная версия"
    assert not TaskReview.objects.filter(submission=submission).exists()
