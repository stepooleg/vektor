"""API-сценарии обратной связи и портфолио (SPEC §6, issue #69)."""

from __future__ import annotations

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.audit.models import AuditLogEntry
from apps.feedback.models import FeedbackRequest, Praise
from apps.notifications.models import Notification
from apps.orgstructure.models import Department, Employee, Position
from apps.portfolio.models import PortfolioEntry
from apps.users.models import Role, User


def _employee(
    code: str,
    *,
    role_code: str = Role.Code.EMPLOYEE.value,
    manager: Employee | None = None,
    active: bool = True,
) -> tuple[Employee, APIClient]:
    """Создать сотрудника с ролью и аутентифицированным клиентом."""
    department, _ = Department.objects.get_or_create(code_1c="FEEDBACK-D", defaults={"name": "ИТ"})
    position, _ = Position.objects.get_or_create(
        code_1c="FEEDBACK-P", defaults={"name": "Специалист"}
    )
    user = User.objects.create_user(email=f"{code.lower()}@corp.local", password="Strong-Pwd-1")
    role, _ = Role.objects.get_or_create(code=role_code, defaults={"name": role_code})
    user.roles.add(role)
    employee = Employee.objects.create(
        code_1c=code,
        user=user,
        last_name="Иванов",
        first_name=code,
        department=department,
        position=position,
        manager=manager,
        is_active=active,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return employee, client


@pytest.mark.django_db
def test_recipient_options_exclude_current_and_inactive_employees() -> None:
    """Форма предлагает только других активных коллег."""
    current, client = _employee("SELF")
    colleague, _ = _employee("ACTIVE")
    inactive, _ = _employee("INACTIVE", active=False)

    response = client.get("/api/v1/feedback/requests/recipients/")

    assert response.status_code == status.HTTP_200_OK
    ids = {item["id"] for item in response.data}
    assert colleague.id in ids
    assert current.id not in ids
    assert inactive.id not in ids


@pytest.mark.django_db
def test_create_praise_sets_sender_records_portfolio_notification_and_audit() -> None:
    """Благодарность создаётся от текущего сотрудника со всеми последствиями."""
    sender, client = _employee("SENDER")
    recipient, _ = _employee("RECIPIENT")

    response = client.post(
        "/api/v1/feedback/praises/",
        {
            "recipient": recipient.id,
            "message": "Спасибо за помощь с релизом!",
            "is_public": True,
            "is_anonymous": False,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    praise = Praise.objects.get(pk=response.data["id"])
    assert praise.sender == sender
    assert PortfolioEntry.objects.filter(
        employee=recipient, type=PortfolioEntry.Type.THANK_YOU.value
    ).exists()
    assert Notification.objects.filter(recipient_email=recipient.user.email).exists()
    assert AuditLogEntry.objects.filter(
        actor=sender.user,
        action="feedback.praise.create",
        target_id=str(praise.id),
    ).exists()


@pytest.mark.django_db
def test_anonymous_praise_does_not_expose_sender_id() -> None:
    """Анонимная благодарность не возвращает идентификатор отправителя."""
    _, client = _employee("SENDER")
    recipient, _ = _employee("RECIPIENT")

    response = client.post(
        "/api/v1/feedback/praises/",
        {
            "recipient": recipient.id,
            "message": "Спасибо!",
            "is_public": True,
            "is_anonymous": True,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["sender_name"] is None
    assert "sender" not in response.data


@pytest.mark.django_db
def test_private_praise_visible_only_to_sender_and_recipient() -> None:
    """Приватную благодарность не видит посторонний сотрудник."""
    sender, sender_client = _employee("SENDER")
    recipient, recipient_client = _employee("RECIPIENT")
    _, outsider_client = _employee("OUTSIDER")
    praise = Praise.objects.create(
        sender=sender,
        recipient=recipient,
        message="Личное спасибо",
        is_public=False,
    )

    assert sender_client.get(f"/api/v1/feedback/praises/{praise.id}/").status_code == 200
    assert recipient_client.get(f"/api/v1/feedback/praises/{praise.id}/").status_code == 200
    assert outsider_client.get(f"/api/v1/feedback/praises/{praise.id}/").status_code == 404


@pytest.mark.django_db
def test_create_feedback_request_sets_requester_notifies_and_audits() -> None:
    """Запрос ОС создаётся от текущего пользователя и журналируется."""
    requester, client = _employee("REQUESTER")
    recipient, _ = _employee("RECIPIENT")

    response = client.post(
        "/api/v1/feedback/requests/",
        {"recipient": recipient.id, "message": "Дай ОС по презентации"},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    feedback_request = FeedbackRequest.objects.get(pk=response.data["id"])
    assert feedback_request.requester == requester
    assert Notification.objects.filter(recipient_email=recipient.user.email).exists()
    assert AuditLogEntry.objects.filter(
        actor=requester.user,
        action="feedback.request.create",
        target_id=str(feedback_request.id),
    ).exists()


@pytest.mark.django_db
def test_feedback_history_cannot_be_modified_or_deleted() -> None:
    """История благодарностей и запросов доступна только для добавления и чтения."""
    sender, client = _employee("SENDER")
    recipient, _ = _employee("RECIPIENT")
    praise = Praise.objects.create(sender=sender, recipient=recipient, message="Спасибо")

    assert (
        client.patch(f"/api/v1/feedback/praises/{praise.id}/", {"message": "Другое"}).status_code
        == 405
    )
    assert client.delete(f"/api/v1/feedback/praises/{praise.id}/").status_code == 405


@pytest.mark.django_db
def test_employee_creates_only_own_manual_portfolio_entry() -> None:
    """Подмена employee игнорируется: сотрудник добавляет запись только себе."""
    employee, client = _employee("EMPLOYEE")
    other, _ = _employee("OTHER")

    response = client.post(
        "/api/v1/portfolio/entries/",
        {
            "employee": other.id,
            "type": PortfolioEntry.Type.ACHIEVEMENT.value,
            "title": "Запустил проект",
            "description": "В срок",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    entry = PortfolioEntry.objects.get(pk=response.data["id"])
    assert entry.employee == employee
    assert AuditLogEntry.objects.filter(
        actor=employee.user,
        action="portfolio.entry.create",
        target_id=str(entry.id),
    ).exists()


@pytest.mark.django_db
def test_manager_can_add_and_read_only_subordinate_portfolio() -> None:
    """Руководитель работает с портфолио своей команды, но не чужих сотрудников."""
    manager, client = _employee("MANAGER", role_code=Role.Code.MANAGER.value)
    subordinate, _ = _employee("SUB", manager=manager)
    outsider, _ = _employee("OUTSIDER")

    allowed = client.post(
        "/api/v1/portfolio/entries/",
        {"employee": subordinate.id, "type": "project", "title": "Проект команды"},
        format="json",
    )
    forbidden = client.post(
        "/api/v1/portfolio/entries/",
        {"employee": outsider.id, "type": "project", "title": "Чужой проект"},
        format="json",
    )
    outsider_feed = client.get(f"/api/v1/portfolio/entries/?employee={outsider.id}")

    assert allowed.status_code == status.HTTP_201_CREATED
    assert forbidden.status_code == status.HTTP_403_FORBIDDEN
    assert outsider_feed.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_manual_portfolio_cannot_spoof_automatic_entry_type() -> None:
    """Курс и благодарность попадают в портфолио только автоматически."""
    _, client = _employee("EMPLOYEE")

    response = client.post(
        "/api/v1/portfolio/entries/",
        {"type": PortfolioEntry.Type.COURSE_PASSED.value, "title": "Поддельный курс"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
