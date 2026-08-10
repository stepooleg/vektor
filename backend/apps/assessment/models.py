"""Модели модуля оценки 360° (SPEC §5).

Домен ``assessment`` — циклы оценки, участники, оценщики и сырые ответы.

Критично для анонимности (SPEC §6.3, §12, 152-ФЗ):
- ``AssessmentResponse`` хранит СЫРЫЕ ответы оценщиков; доступны ТОЛЬКО
  системному audit-log, никогда — UI/API для HR/руководителя/сотрудника.
- Публичный доступ — только через агрегаты (см. services.py, issue #12).
- Порог анонимности (минимум оценщиков в группе) применяется при агрегации.

Жизненный цикл цикла (SPEC §5.2):
created → assigned → in_progress → collecting → aggregated → closed.
"""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.competencies.models import Competency
from apps.orgstructure.models import Employee
from apps.users.models import User


class AssessmentCycle(models.Model):
    """Цикл оценки 360° (SPEC §5.1.1, §5.2).

    Создаётся HR: выбор периода, сроков, состава участников и порога анонимности.
    """

    class Status(models.TextChoices):
        CREATED = "created", _("Создан")
        ASSIGNED = "assigned", _("Оценщики назначены")
        IN_PROGRESS = "in_progress", _("Идёт оценка")
        COLLECTING = "collecting", _("Сбор ответов завершается")
        AGGREGATED = "aggregated", _("Результаты рассчитаны")
        CLOSED = "closed", _("Закрыт")

    name = models.CharField(_("Название цикла"), max_length=200)
    framework = models.ForeignKey(
        "competencies.CompetencyFramework",
        on_delete=models.PROTECT,
        related_name="cycles",
        null=True,
        blank=True,
        verbose_name=_("Модель компетенций"),
    )
    status = models.CharField(
        _("Статус"), max_length=16, choices=Status.choices, default=Status.CREATED
    )
    # Порог анонимности: минимум оценщиков в группе для показа агрегата (SPEC §5.1.1).
    anonymity_threshold = models.PositiveSmallIntegerField(
        _("Порог анонимности (мин. оценщиков в группе)"),
        default=3,
    )
    start_date = models.DateField(_("Дата начала"), null=True, blank=True)
    deadline = models.DateField(_("Дедлайн"), null=True, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_cycles",
        verbose_name=_("Создал"),
    )
    created_at = models.DateTimeField(_("Создан"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Обновлён"), auto_now=True)

    class Meta:
        verbose_name = _("Цикл оценки")
        verbose_name_plural = _("Циклы оценки")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        """Название цикла."""
        return self.name


class Participant(models.Model):
    """Оцениваемый сотрудник в цикле (SPEC §5.1.1).

    Один участник = один сотрудник, которого оценивают окружающие.
    """

    cycle = models.ForeignKey(
        AssessmentCycle,
        on_delete=models.CASCADE,
        related_name="participants",
        verbose_name=_("Цикл"),
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="assessment_participations",
        verbose_name=_("Оцениваемый сотрудник"),
    )

    class Meta:
        verbose_name = _("Участник цикла")
        verbose_name_plural = _("Участники цикла")
        unique_together = [("cycle", "employee")]

    def __str__(self) -> str:
        """Цикл и сотрудник."""
        return f"{self.cycle} — {self.employee}"


class ReviewerAssignment(models.Model):
    """Назначение оценщика на участника цикла с указанием группы (SPEC §5.1.1).

    Группы оценщиков:
    - ``manager`` — руководитель (обязательная группа для цикла);
    - ``peer`` — коллеги (одного уровня);
    - ``subordinate`` — подчинённые;
    - ``self`` — самооценка (см. SPEC §5.1.2, issue #11).
    """

    class Group(models.TextChoices):
        MANAGER = "manager", _("Руководитель")
        PEER = "peer", _("Коллега")
        SUBORDINATE = "subordinate", _("Подчинённый")
        SELF = "self", _("Самооценка")

    cycle = models.ForeignKey(
        AssessmentCycle,
        on_delete=models.CASCADE,
        related_name="reviewer_assignments",
        verbose_name=_("Цикл"),
    )
    participant = models.ForeignKey(
        Participant,
        on_delete=models.CASCADE,
        related_name="reviewer_assignments",
        verbose_name=_("Оцениваемый"),
    )
    reviewer = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="reviewer_assignments",
        verbose_name=_("Оценщик"),
    )
    group = models.CharField(_("Группа оценщиков"), max_length=16, choices=Group.choices)
    completed = models.BooleanField(_("Оценка заполнена"), default=False)
    completed_at = models.DateTimeField(_("Заполнена"), null=True, blank=True)

    class Meta:
        verbose_name = _("Назначение оценщика")
        verbose_name_plural = _("Назначения оценщиков")
        unique_together = [("cycle", "participant", "reviewer")]
        # Один оценщик не может быть в двух группах для одного участника.
        constraints = [
            models.UniqueConstraint(
                fields=["cycle", "participant", "reviewer"],
                name="unique_reviewer_per_participant",
            ),
        ]

    def __str__(self) -> str:
        """Группа, оценщик и участник."""
        return f"[{self.get_group_display()}] {self.reviewer} → {self.participant.employee}"


class ExpectedLevel(models.Model):
    """Ожидаемый уровень компетенции для должности (SPEC §5.1.3 — матрица).

    Привязка «компетенция × должность → ожидаемый уровень шкалы». Используется
    для сравнения «текущий vs ожидаемый» и выявления зон развития (SPEC §8.1).
    Выставляется HR/методологом.
    """

    position = models.ForeignKey(
        "orgstructure.Position",
        on_delete=models.CASCADE,
        related_name="expected_levels",
        verbose_name=_("Должность"),
    )
    competency = models.ForeignKey(
        Competency,
        on_delete=models.CASCADE,
        related_name="expected_levels",
        verbose_name=_("Компетенция"),
    )
    expected_level = models.PositiveSmallIntegerField(_("Ожидаемый уровень шкалы"))

    class Meta:
        verbose_name = _("Ожидаемый уровень")
        verbose_name_plural = _("Ожидаемые уровни")
        unique_together = [("position", "competency")]

    def __str__(self) -> str:
        """Должность, компетенция и уровень."""
        return f"{self.position} / {self.competency}: {self.expected_level}"


class AssessmentResponse(models.Model):
    """СЫРОЙ ответ оценщика по компетенции (SPEC §5.3, §6.3 — КРИТИЧНО).

    ВНИМАНИЕ: эта модель хранит индивидуальные ответы оценщиков. Доступ к ней
    из UI/API запрещён всем, кроме системного audit-log. Публичные данные —
    только агрегаты (services.py, issue #12).
    """

    assignment = models.ForeignKey(
        ReviewerAssignment,
        on_delete=models.CASCADE,
        related_name="responses",
        verbose_name=_("Назначение"),
    )
    competency = models.ForeignKey(
        Competency,
        on_delete=models.PROTECT,
        related_name="responses",
        verbose_name=_("Компетенция"),
    )
    score = models.PositiveSmallIntegerField(_("Оценка по шкале"))
    created_at = models.DateTimeField(_("Создан"), auto_now_add=True)

    class Meta:
        verbose_name = _("Сырой ответ оценки")
        verbose_name_plural = _("Сырые ответы оценки")
        unique_together = [("assignment", "competency")]
        # Сырые ответы не должны запрашиваться «случайно» — индекс для аудита.
        indexes = [
            models.Index(fields=["assignment"], name="resp_assignment_idx"),
        ]

    def __str__(self) -> str:
        """Компетенция и оценка (без оценщика — для безопасности логов)."""
        return f"{self.competency}: {self.score}"


class AssessmentComment(models.Model):
    """Качественный комментарий оценщика (SPEC §5.3).

    Как и ``AssessmentResponse`` — СЫРЫЕ данные, недоступны никому, кроме
    audit-log. В агрегатах могут показываться обезличенно при достаточном
    количестве оценщиков в группе (см. services.py).
    """

    assignment = models.ForeignKey(
        ReviewerAssignment,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name=_("Назначение"),
    )
    text = models.TextField(_("Текст комментария"))
    is_general = models.BooleanField(
        _("Общий комментарий (не по конкретной компетенции)"),
        default=False,
    )
    competency = models.ForeignKey(
        Competency,
        on_delete=models.PROTECT,
        related_name="comments",
        null=True,
        blank=True,
        verbose_name=_("Компетенция (если комментарий по ней)"),
    )
    created_at = models.DateTimeField(_("Создан"), auto_now_add=True)

    class Meta:
        verbose_name = _("Комментарий оценки")
        verbose_name_plural = _("Комментарии оценки")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        """Краткое представление (без оценщика — безопасность логов)."""
        snippet = self.text[:50] if self.text else ""
        return f"Комментарий: {snippet}"


# ===========================================================================
# MBO / OKR — целеполагание (SPEC v1.1 §16.4, issue #37)
# ===========================================================================


class Objective(models.Model):
    """Цель сотрудника (MBO/OKR, SPEC v1.1 §16.4).

    Цель привязана к сотруднику, периоду (квартал/год) и может быть связана
    с циклом оценки. Завершённые/просроченные цели влияют на оценку.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", _("Черновик")
        ACTIVE = "active", _("Активна")
        COMPLETED = "completed", _("Завершена")
        OVERDUE = "overdue", _("Просрочена")

    class Period(models.TextChoices):
        Q1 = "Q1", _("Q1")
        Q2 = "Q2", _("Q2")
        Q3 = "Q3", _("Q3")
        Q4 = "Q4", _("Q4")
        YEAR = "YEAR", _("Год")

    employee = models.ForeignKey(
        "orgstructure.Employee",
        on_delete=models.CASCADE,
        related_name="objectives",
        verbose_name=_("Сотрудник"),
    )
    title = models.CharField(_("Цель"), max_length=300)
    description = models.TextField(_("Описание"), blank=True)
    period = models.CharField(
        _("Период"), max_length=8, choices=Period.choices, default=Period.YEAR
    )
    year = models.PositiveSmallIntegerField(_("Год"), default=2026)
    status = models.CharField(
        _("Статус"), max_length=16, choices=Status.choices, default=Status.DRAFT
    )
    # Связь с циклом оценки (влияет на оценку, SPEC v1.1).
    cycle = models.ForeignKey(
        AssessmentCycle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="objectives",
        verbose_name=_("Цикл оценки"),
    )
    created_at = models.DateTimeField(_("Создана"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Обновлена"), auto_now=True)

    class Meta:
        verbose_name = _("Цель (MBO/OKR)")
        verbose_name_plural = _("Цели (MBO/OKR)")
        ordering = ["-year", "-created_at"]

    def __str__(self) -> str:
        """Цель и период."""
        return f"{self.title} ({self.period} {self.year})"

    @property
    def progress_percent(self) -> int:
        """Прогресс цели = средний прогресс ключевых результатов (%)."""
        krs = self.key_results.all()
        if not krs:
            return 0
        return int(sum(kr.progress_percent for kr in krs) / krs.count())


class KeyResult(models.Model):
    """Ключевой результат цели (KR, SPEC v1.1 §16.4).

    Прогресс: текущее значение относительно целевого.
    """

    objective = models.ForeignKey(
        Objective,
        on_delete=models.CASCADE,
        related_name="key_results",
        verbose_name=_("Цель"),
    )
    title = models.CharField(_("KR"), max_length=300)
    target_value = models.FloatField(_("Целевое значение"), default=100)
    current_value = models.FloatField(_("Текущее значение"), default=0)
    created_at = models.DateTimeField(_("Создан"), auto_now_add=True)

    class Meta:
        verbose_name = _("Ключевой результат")
        verbose_name_plural = _("Ключевые результаты")
        ordering = ["objective", "id"]

    def __str__(self) -> str:
        """KR и прогресс."""
        return f"{self.title}: {self.current_value}/{self.target_value}"

    @property
    def progress_percent(self) -> int:
        """Процент выполнения KR."""
        if self.target_value == 0:
            return 100 if self.current_value > 0 else 0
        return min(100, int(self.current_value / self.target_value * 100))
