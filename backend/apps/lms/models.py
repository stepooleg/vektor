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


class Lesson(models.Model):
    """Урок курса — текстовый материал или тест (SPEC §7.2, §7.3).

    Порядок в курсе задаётся полем ``order`` (редактор, SPEC §7.3).
    """

    class Type(models.TextChoices):
        TEXT = "text", _("Текстовый материал")
        QUIZ = "quiz", _("Тест")

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="lessons",
        verbose_name=_("Курс"),
    )
    title = models.CharField(_("Название"), max_length=300)
    type = models.CharField(_("Тип"), max_length=8, choices=Type.choices)
    order = models.PositiveSmallIntegerField(_("Порядок"), default=0)
    # Текстовый материал (для type=text).
    content = models.TextField(_("Содержание (текст)"), blank=True)
    # Настройки теста (для type=quiz, SPEC §7.2).
    pass_score = models.PositiveSmallIntegerField(_("Проходной балл, %"), default=80)
    max_attempts = models.PositiveSmallIntegerField(_("Максимум попыток"), default=3)
    shuffle_questions = models.BooleanField(_("Перемешивать вопросы"), default=False)

    class Meta:
        verbose_name = _("Урок")
        verbose_name_plural = _("Уроки")
        ordering = ["course", "order", "id"]
        unique_together = [("course", "order")]

    def __str__(self) -> str:
        """Название урока."""
        return self.title


class Question(models.Model):
    """Вопрос теста (SPEC §7.2).

    Типы: один ответ / несколько ответов / шкала / текст.
    Для «текст» автопроверка невозможна (требует куратора).
    """

    class Type(models.TextChoices):
        SINGLE = "single", _("Один ответ")
        MULTIPLE = "multiple", _("Несколько ответов")
        SCALE = "scale", _("Шкала")
        TEXT = "text", _("Текстовый ответ")

    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name="questions",
        verbose_name=_("Урок"),
        limit_choices_to={"type": "quiz"},
    )
    text = models.TextField(_("Текст вопроса"))
    type = models.CharField(_("Тип"), max_length=8, choices=Type.choices)
    order = models.PositiveSmallIntegerField(_("Порядок"), default=0)
    # Балл за вопрос (для расчёта результата).
    score = models.PositiveSmallIntegerField(_("Балл"), default=1)

    class Meta:
        verbose_name = _("Вопрос")
        verbose_name_plural = _("Вопросы")
        ordering = ["lesson", "order", "id"]

    def __str__(self) -> str:
        """Краткий текст вопроса."""
        return self.text[:80]


class AnswerOption(models.Model):
    """Вариант ответа на вопрос (для single/multiple, SPEC §7.2).

    ``is_correct`` — флаг правильного варианта (для автопроверки).
    """

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="options",
        verbose_name=_("Вопрос"),
    )
    text = models.CharField(_("Текст варианта"), max_length=500)
    is_correct = models.BooleanField(_("Правильный"), default=False)
    order = models.PositiveSmallIntegerField(_("Порядок"), default=0)

    class Meta:
        verbose_name = _("Вариант ответа")
        verbose_name_plural = _("Варианты ответов")
        ordering = ["question", "order", "id"]

    def __str__(self) -> str:
        """Текст варианта."""
        return self.text


class PracticalTask(models.Model):
    """Практическое задание курса с проверкой куратором (SPEC §7.2).

    Сотрудник прикрепляет ответ (текст/файл); куратор проверяет, оставляет
    комментарий и оценку («зачёт/незачёт» или по шкале).
    """

    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name="practical_tasks",
        verbose_name=_("Урок"),
    )
    title = models.CharField(_("Название задания"), max_length=300)
    description = models.TextField(_("Описание задания"))
    # Ответственный куратор (назначается Методологом/HR).
    reviewer = models.ForeignKey(
        "orgstructure.Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tasks_to_review",
        verbose_name=_("Куратор"),
    )

    class Meta:
        verbose_name = _("Практическое задание")
        verbose_name_plural = _("Практические задания")
        ordering = ["lesson", "id"]

    def __str__(self) -> str:
        """Название задания."""
        return self.title


class Submission(models.Model):
    """Ответ сотрудника на практическое задание (SPEC §7.2).

    Жизненный цикл: submitted → in_review → reviewed.
    """

    class Status(models.TextChoices):
        SUBMITTED = "submitted", _("Отправлено")
        IN_REVIEW = "in_review", _("На проверке")
        REVIEWED = "reviewed", _("Проверено")

    task = models.ForeignKey(
        PracticalTask,
        on_delete=models.CASCADE,
        related_name="submissions",
        verbose_name=_("Задание"),
    )
    # Кто сдал ответ.
    employee = models.ForeignKey(
        "orgstructure.Employee",
        on_delete=models.CASCADE,
        related_name="task_submissions",
        verbose_name=_("Сотрудник"),
    )
    answer_text = models.TextField(_("Текст ответа"), blank=True)
    # TODO(#21): прикрепление файла (FileField + storage) — добавить при UI.
    status = models.CharField(
        _("Статус"),
        max_length=16,
        choices=Status.choices,
        default=Status.SUBMITTED,
    )
    submitted_at = models.DateTimeField(_("Отправлено"), auto_now_add=True)
    reviewed_at = models.DateTimeField(_("Проверено"), null=True, blank=True)

    class Meta:
        verbose_name = _("Ответ на задание")
        verbose_name_plural = _("Ответы на задания")
        ordering = ["-submitted_at"]
        unique_together = [("task", "employee")]

    def __str__(self) -> str:
        """Задание и сотрудник."""
        return f"{self.task} — {self.employee}"


class TaskReview(models.Model):
    """Оценка куратора практического задания (SPEC §7.2).

    «Зачёт/незачёт» (``passed``) или по шкале (``score``).
    """

    submission = models.OneToOneField(
        Submission,
        on_delete=models.CASCADE,
        related_name="review",
        verbose_name=_("Ответ"),
    )
    reviewer = models.ForeignKey(
        "orgstructure.Employee",
        on_delete=models.SET_NULL,
        null=True,
        related_name="task_reviews",
        verbose_name=_("Куратор"),
    )
    passed = models.BooleanField(_("Зачтено"), default=False)
    score = models.PositiveSmallIntegerField(_("Оценка по шкале"), null=True, blank=True)
    comment = models.TextField(_("Комментарий куратора"), blank=True)
    created_at = models.DateTimeField(_("Создано"), auto_now_add=True)

    class Meta:
        verbose_name = _("Проверка задания")
        verbose_name_plural = _("Проверки заданий")

    def __str__(self) -> str:
        """Статус зачёта."""
        return f"{'Зачёт' if self.passed else 'Незачёт'}: {self.submission.task}"
