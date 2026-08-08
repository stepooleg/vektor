"""Тесты API каталога курсов (Test-First, SPEC §7.1, §7.3, issue #19).

Контракты:
- поиск по title и фильтр по категории/обязательности;
- сотрудник видит только опубликованные, Методолог/HR — все;
- создание/правка — только Методолог (403 сотруднику);
- фильтр по компетенции возвращает курсы с привязкой.
"""

from __future__ import annotations

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.competencies.models import Competency, CompetencyGroup, Scale
from apps.lms.models import Category, Course, CourseCompetencyLink
from apps.users.models import Role, User


def _user(email: str, role_code: str | None) -> User:
    """Создать пользователя с ролью (или без)."""
    user = User.objects.create_user(email=email, password="Strong-Pwd-1")
    if role_code:
        role, _ = Role.objects.get_or_create(code=role_code, defaults={"name": role_code})
        user.roles.add(role)
    return user


@pytest.mark.django_db
def test_employee_sees_only_published_courses() -> None:
    """Сотрудник видит только опубликованные курсы (SPEC §7.1)."""
    Course.objects.create(title="Опубликован", status=Course.Status.PUBLISHED.value)
    Course.objects.create(title="Черновик", status=Course.Status.DRAFT.value)
    user = _user("emp@corp.local", Role.Code.EMPLOYEE.value)
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get("/api/v1/lms/courses/")

    titles = [c["title"] for c in response.data["results"]]
    assert "Опубликован" in titles
    assert "Черновик" not in titles


@pytest.mark.django_db
def test_methodologist_sees_all_courses() -> None:
    """Методолог видит все курсы, включая черновики."""
    Course.objects.create(title="Опубл", status=Course.Status.PUBLISHED.value)
    Course.objects.create(title="Черновик", status=Course.Status.DRAFT.value)
    user = _user("meth@corp.local", Role.Code.METHODOLOGIST.value)
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get("/api/v1/lms/courses/")

    assert response.data["count"] >= 2


@pytest.mark.django_db
def test_search_by_title() -> None:
    """Поиск по названию (icontains)."""
    Course.objects.create(title="Python для новичков", status=Course.Status.PUBLISHED.value)
    Course.objects.create(title="Java основы", status=Course.Status.PUBLISHED.value)
    user = _user("u@corp.local", Role.Code.EMPLOYEE.value)
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get("/api/v1/lms/courses/?search=Python")

    titles = [c["title"] for c in response.data["results"]]
    assert "Python для новичков" in titles
    assert "Java основы" not in titles


@pytest.mark.django_db
def test_filter_by_category() -> None:
    """Фильтрация по категории."""
    cat = Category.objects.create(name="IT")
    Course.objects.create(title="В категории", category=cat, status=Course.Status.PUBLISHED.value)
    Course.objects.create(title="Без категории", status=Course.Status.PUBLISHED.value)
    user = _user("u@corp.local", Role.Code.EMPLOYEE.value)
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get(f"/api/v1/lms/courses/?category={cat.id}")

    titles = [c["title"] for c in response.data["results"]]
    assert "В категории" in titles
    assert "Без категории" not in titles


@pytest.mark.django_db
def test_filter_by_competency() -> None:
    """Фильтр по компетенции возвращает курсы с привязкой (SPEC §7.1, §8.1)."""
    scale = Scale.objects.create(name="Ш", min_value=1, max_value=5)
    group = CompetencyGroup.objects.create(name="Г")
    comp = Competency.objects.create(name="К", group=group, scale=scale)
    course_with = Course.objects.create(title="С привязкой", status=Course.Status.PUBLISHED.value)
    Course.objects.create(title="Без привязки", status=Course.Status.PUBLISHED.value)
    CourseCompetencyLink.objects.create(course=course_with, competency=comp)
    user = _user("u@corp.local", Role.Code.EMPLOYEE.value)
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.get(f"/api/v1/lms/courses/?competency={comp.id}")

    titles = [c["title"] for c in response.data["results"]]
    assert titles == ["С привязкой"]


@pytest.mark.django_db
def test_employee_cannot_create_course() -> None:
    """Сотрудник не может создавать курсы (403)."""
    user = _user("emp@corp.local", Role.Code.EMPLOYEE.value)
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post("/api/v1/lms/courses/", {"title": "Курс"}, format="json")

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_methodologist_can_create_course() -> None:
    """Методолог создаёт курс (SPEC §7.3)."""
    user = _user("meth@corp.local", Role.Code.METHODOLOGIST.value)
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post("/api/v1/lms/courses/", {"title": "Новый курс"}, format="json")

    assert response.status_code == status.HTTP_201_CREATED
