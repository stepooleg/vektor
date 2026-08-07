"""Модели LMS — каталог курсов (SPEC §7.1).

Домен ``lms`` — встроенное обучение: каталог курсов по категориям,
учебные материалы (тексты/тесты), практические задания, прогресс и
сертификация (см. последующие модели в этом модуле).

Привязка курса к компетенциям (``CourseCompetencyLink``) — основа для
автоподбора индивидуальных планов развития (SPEC §8.1).
"""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.competencies.models import Competency


class Category(models.Model):
    """Категория каталога курсов (иерархическая, SPEC §7.1).

    Дерево через ``parent``. ``code`` — стабильный идентификатор.
    """

    name = models.CharField(_("Название"), max_length=200)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="children",
        null=True,
        blank=True,
        verbose_name=_("Родительская категория"),
    )

    class Meta:
        verbose_name = _("Категория курсов")
        verbose_name_plural = _("Категории курсов")
        ordering = ["name"]
        unique_together = [("name", "parent")]

    def __str__(self) -> str:
        """Название категории."""
        return self.name


class Course(models.Model):
    """Курс обучения (SPEC §7.1, §7.3).

    Создаётся Методологом; проходит статусы: черновик → опубликован → архив.
    Обязательный курс назначается сотруднику/роли (см. ``Enrollment``).
    """

    class Status(models.TextChoices):
        DRAFT = "draft", _("Черновик")
        PUBLISHED = "published", _("Опубликован")
        ARCHIVED = "archived", _("В архиве")

    title = models.CharField(_("Название"), max_length=300)
    description = models.TextField(_("Описание"), blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="courses",
        verbose_name=_("Категория"),
    )
    status = models.CharField(
        _("Статус"), max_length=16, choices=Status.choices, default=Status.DRAFT
    )
    # Обязательный (назначенный) или добровольный курс (SPEC §7.1).
    is_mandatory = models.BooleanField(_("Обязательный"), default=False)
    # Минимальный проходной % для статуса «пройдён» (SPEC §7.4).
    pass_threshold = models.PositiveSmallIntegerField(_("Проходной порог, %"), default=80)
    created_at = models.DateTimeField(_("Создан"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Обновлён"), auto_now=True)

    class Meta:
        verbose_name = _("Курс")
        verbose_name_plural = _("Курсы")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        """Название курса."""
        return self.title

    @property
    def is_available(self) -> bool:
        """Доступен ли курс слушателям (опубликован и не в архиве)."""
        return self.status == Course.Status.PUBLISHED.value


class CourseCompetencyLink(models.Model):
    """Привязка курса к компетенции (SPEC §7.1, §8.1).

    Используется для автоподбора курсов в ИПР по зонам развития.
    """

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="competency_links",
        verbose_name=_("Курс"),
    )
    competency = models.ForeignKey(
        Competency,
        on_delete=models.CASCADE,
        related_name="course_links",
        verbose_name=_("Компетенция"),
    )

    class Meta:
        verbose_name = _("Привязка курса к компетенции")
        verbose_name_plural = _("Привязки курсов к компетенциям")
        unique_together = [("course", "competency")]

    def __str__(self) -> str:
        """Курс и компетенция."""
        return f"{self.course} → {self.competency}"
