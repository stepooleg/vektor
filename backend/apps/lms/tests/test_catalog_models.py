"""Тесты моделей каталога курсов (Test-First, SPEC §7.1, issue #19).

Контракты:
- иерархия категорий строится (дерево через parent);
- курс создаётся со статусом draft по умолчанию;
- привязка курса к компетенции работает;
- is_available = True только для опубликованных.
"""

from __future__ import annotations

import pytest

from apps.competencies.models import Competency, CompetencyGroup, Scale
from apps.lms.models import Category, Course, CourseCompetencyLink


@pytest.mark.django_db
def test_category_tree_builds() -> None:
    """Иерархия категорий строится по parent (SPEC §7.1)."""
    root = Category.objects.create(name="IT")
    sub = Category.objects.create(name="Разработка", parent=root)

    assert sub.parent_id == root.id
    assert root.children.count() == 1


@pytest.mark.django_db
def test_course_default_status_is_draft() -> None:
    """Курс создаётся со статусом draft (SPEC §7.3 — черновик по умолчанию)."""
    course = Course.objects.create(title="Введение в Vektor")

    assert course.status == Course.Status.DRAFT.value
    assert course.is_mandatory is False
    assert course.is_available is False


@pytest.mark.django_db
def test_published_course_is_available() -> None:
    """Опубликованный курс доступен слушателям."""
    course = Course.objects.create(title="Курс", status=Course.Status.PUBLISHED.value)
    assert course.is_available is True


@pytest.mark.django_db
def test_course_competency_link() -> None:
    """Привязка курса к компетенции сохраняется (SPEC §7.1, §8.1)."""
    scale = Scale.objects.create(name="Ш", min_value=1, max_value=5)
    group = CompetencyGroup.objects.create(name="Г")
    competency = Competency.objects.create(name="К", group=group, scale=scale)
    course = Course.objects.create(title="Курс по К")

    link = CourseCompetencyLink.objects.create(course=course, competency=competency)

    assert link.competency_id == competency.id
    assert course.competency_links.count() == 1
    # Обратная связь: через competency.course_links.
    assert competency.course_links.count() == 1


@pytest.mark.django_db
def test_unique_link_per_course_competency() -> None:
    """Повторная привязка того же курса к той же компетенции невозможна."""
    from django.db import IntegrityError

    scale = Scale.objects.create(name="Ш", min_value=1, max_value=5)
    group = CompetencyGroup.objects.create(name="Г")
    competency = Competency.objects.create(name="К", group=group, scale=scale)
    course = Course.objects.create(title="Курс")
    CourseCompetencyLink.objects.create(course=course, competency=competency)

    with pytest.raises(IntegrityError):
        CourseCompetencyLink.objects.create(course=course, competency=competency)
