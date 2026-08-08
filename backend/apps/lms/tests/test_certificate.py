"""Тесты PDF-сертификатов (Test-First, SPEC §7.4, Фаза 4 #38).

Контракты:
- PDF-сертификат генерируется (корректная сигнатура PDF);
- сертификат создаётся при завершении курса (уникальный код);
- повторная генерация идемпотентна (один сертификат на курс+сотрудник);
- сертификат содержит ФИО, название курса, дату.
"""

from __future__ import annotations

import pytest

from apps.lms.certificate import generate_certificate_pdf
from apps.lms.models import Certificate, Course, Enrollment, Lesson
from apps.orgstructure.models import Department, Employee, Position
from apps.users.models import User


def _completed_enrollment() -> tuple[Enrollment, Employee, Course]:
    """Создать завершённую запись на курс."""
    dept = Department.objects.create(code_1c="D1", name="ИТ")
    pos = Position.objects.create(code_1c="P1", name="Разработчик")
    user = User.objects.create_user(email="alice@corp.local", password="Strong-Pwd-1")
    emp = Employee.objects.create(
        code_1c="E1",
        user=user,
        last_name="Иванова",
        first_name="Анна",
        department=dept,
        position=pos,
    )
    course = Course.objects.create(
        title="Python для новичков", status=Course.Status.PUBLISHED.value
    )
    Lesson.objects.create(course=course, title="Урок 1", type=Lesson.Type.TEXT.value, order=1)
    enrollment = Enrollment.objects.create(
        course=course,
        employee=emp,
        status=Enrollment.Status.COMPLETED.value,
        progress_percent=100,
    )
    return enrollment, emp, course


@pytest.mark.django_db
def test_generate_certificate_pdf_returns_valid_pdf() -> None:
    """PDF-сертификат генерируется с корректной сигнатурой."""
    enrollment, emp, course = _completed_enrollment()

    pdf_bytes = generate_certificate_pdf(enrollment)

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500  # не пустой


@pytest.mark.django_db
def test_certificate_created_on_completion() -> None:
    """Сертификат создаётся при завершении курса (SPEC §7.4)."""
    enrollment, _, _ = _completed_enrollment()

    from apps.lms.certificate import issue_certificate

    cert = issue_certificate(enrollment)

    assert cert.enrollment_id == enrollment.id
    assert cert.code  # уникальный код
    assert cert.employee_full_name == "Иванова Анна"
    assert cert.course_title == "Python для новичков"


@pytest.mark.django_db
def test_certificate_idempotent() -> None:
    """Повторная генерация возвращает тот же сертификат (без дублей)."""
    enrollment, _, _ = _completed_enrollment()
    from apps.lms.certificate import issue_certificate

    cert1 = issue_certificate(enrollment)
    cert2 = issue_certificate(enrollment)

    assert cert1.id == cert2.id
    assert Certificate.objects.filter(enrollment=enrollment).count() == 1


@pytest.mark.django_db
def test_certificate_has_unique_code() -> None:
    """Каждый сертификат имеет уникальный код."""
    enrollment, _, _ = _completed_enrollment()
    from apps.lms.certificate import issue_certificate

    cert = issue_certificate(enrollment)

    assert len(cert.code) >= 8
    assert Certificate.objects.filter(code=cert.code).count() == 1
