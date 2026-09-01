"""API каталога курсов (DRF, SPEC §7.1, §7.3, issue #19).

Права:
- список курсов: аутентифицированным; сотрудник видит только опубликованные,
  Методолог/HR — все (включая черновики);
- создание/правка/удаление: Методолог (SPEC §7.3);
- категории: чтение всем, правка — Методолог.

Поиск: по title (icontains). Фильтры: category, competency, is_mandatory.
"""

from __future__ import annotations

from pathlib import Path

from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django_filters import rest_framework as filters
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.request import Request
from rest_framework.response import Response

from apps.orgstructure.models import Employee
from apps.users.models import Role
from apps.users.permissions import IsAuthenticatedUser, IsMethodologist

from .models import Category, Course, Enrollment, Lesson, LessonProgress, PracticalTask, Submission
from .serializers import (
    CategorySerializer,
    CourseSerializer,
    EnrollmentSerializer,
    SubmissionSerializer,
    TaskReviewSerializer,
)
from .services import (
    ReviewAlreadyCompleted,
    ReviewNotAllowed,
    can_review_submission,
    check_attempt_allowed,
    get_review_queue,
    grade_quiz,
    mark_lesson_completed,
    review_submission,
    submit_practical_task,
)


def _current_employee(request: Request) -> Employee:
    """Вернуть профиль сотрудника текущего пользователя."""
    user_id = getattr(request.user, "pk", None)
    if user_id is None:
        raise NotFound("Профиль сотрудника не найден.")
    employee = Employee.objects.filter(user_id=user_id).first()
    if employee is None:
        raise NotFound("Профиль сотрудника не найден.")
    return employee


class CourseFilter(filters.FilterSet):
    """Фильтры каталога курсов: категория, компетенция, обязательность."""

    # Привязка к компетенции проверяется через competency_links.
    competency = filters.NumberFilter(field_name="competency_links__competency_id")

    class Meta:
        """Метаданные фильтра курсов."""

        model = Course
        fields = ["category", "is_mandatory"]


class CategoryViewSet(viewsets.ModelViewSet[Category]):
    """CRUD категорий каталога: чтение всем, правка — Методолог."""

    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    def get_permissions(self):  # type: ignore[no-untyped-def]
        """Чтение — аутентифицированным; запись — Методолог."""
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsMethodologist()]
        return [IsAuthenticatedUser()]


class CourseViewSet(viewsets.ModelViewSet[Course]):
    """CRUD курсов с поиском и фильтрами (SPEC §7.1)."""

    serializer_class = CourseSerializer
    filterset_class = CourseFilter
    filter_backends = [SearchFilter, OrderingFilter, filters.DjangoFilterBackend]
    search_fields = ["title", "description"]
    ordering_fields = ["created_at", "title"]

    def get_queryset(self):  # type: ignore[no-untyped-def]
        """Сотрудник видит только опубликованные; Методолог/HR — все."""
        qs = (
            Course.objects.select_related("category")
            .prefetch_related("lessons__questions__options")
            .distinct()
        )
        user = self.request.user
        is_staff = getattr(user, "is_authenticated", False)
        if is_staff and user.has_any_role(  # type: ignore[union-attr]
            Role.Code.METHODOLOGIST.value,
            Role.Code.HR.value,
        ):
            return qs
        return qs.filter(status=Course.Status.PUBLISHED.value)

    def get_permissions(self):  # type: ignore[no-untyped-def]
        """Чтение — аутентифицированным; запись — Методолог."""
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsMethodologist()]
        return [IsAuthenticatedUser()]

    @action(detail=False, methods=["get"], url_path="my")
    def my_learning(self, request: Request) -> Response:
        """Вернуть курсы и прогресс текущего сотрудника."""
        employee = _current_employee(request)
        enrollments = (
            Enrollment.objects.filter(employee=employee)
            .select_related("course", "certificate")
            .prefetch_related("lesson_progresses")
        )
        return Response(EnrollmentSerializer(enrollments, many=True).data)

    @action(detail=True, methods=["post"])
    def enroll(self, request: Request, pk: str | None = None) -> Response:
        """Идемпотентно записать сотрудника на опубликованный курс."""
        course = self.get_object()
        if not course.is_available:
            raise ValidationError("Записаться можно только на опубликованный курс.")
        enrollment, created = Enrollment.objects.get_or_create(
            course=course,
            employee=_current_employee(request),
        )
        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(EnrollmentSerializer(enrollment).data, status=response_status)

    def _enrollment_for_lesson(
        self, request: Request, course: Course, lesson_id: str
    ) -> tuple[Enrollment, Lesson]:
        """Проверить принадлежность урока и наличие записи на курс."""
        lesson = get_object_or_404(Lesson, pk=lesson_id, course=course)
        enrollment = get_object_or_404(
            Enrollment,
            course=course,
            employee=_current_employee(request),
        )
        return enrollment, lesson

    @action(
        detail=True,
        methods=["post"],
        url_path=r"lessons/(?P<lesson_id>[^/.]+)/complete",
    )
    def complete_lesson(
        self, request: Request, pk: str | None = None, lesson_id: str = ""
    ) -> Response:
        """Отметить текстовый материал прочитанным."""
        enrollment, lesson = self._enrollment_for_lesson(request, self.get_object(), lesson_id)
        if lesson.type != Lesson.Type.TEXT.value:
            raise ValidationError("Тест завершается только после успешной проверки ответов.")
        mark_lesson_completed(enrollment, lesson)
        enrollment.refresh_from_db()
        return Response(EnrollmentSerializer(enrollment).data)

    @action(
        detail=True,
        methods=["post"],
        url_path=r"lessons/(?P<lesson_id>[^/.]+)/submit-quiz",
    )
    def submit_quiz(self, request: Request, pk: str | None = None, lesson_id: str = "") -> Response:
        """Проверить ответы теста и обновить прогресс при успехе."""
        enrollment, lesson = self._enrollment_for_lesson(request, self.get_object(), lesson_id)
        if lesson.type != Lesson.Type.QUIZ.value:
            raise ValidationError("Этот урок не является тестом.")
        raw_answers = request.data.get("answers")
        if not isinstance(raw_answers, dict):
            raise ValidationError({"answers": "Передайте ответы по вопросам."})
        try:
            answers = {
                int(question_id): [int(option_id) for option_id in option_ids]
                for question_id, option_ids in raw_answers.items()
                if isinstance(option_ids, list)
            }
        except (TypeError, ValueError) as error:
            raise ValidationError({"answers": "Некорректный формат ответов."}) from error

        result = grade_quiz(lesson, answers)
        progress, _ = LessonProgress.objects.get_or_create(
            enrollment=enrollment,
            lesson=lesson,
        )
        if not check_attempt_allowed(lesson, attempts_used=progress.attempts_used):
            raise ValidationError("Лимит попыток теста исчерпан.")
        progress.attempts_used += 1
        progress.best_score = max(progress.best_score, result.percent)
        progress.save(update_fields=["attempts_used", "best_score", "updated_at"])
        if result.passed:
            mark_lesson_completed(enrollment, lesson)
        enrollment.refresh_from_db()
        return Response(
            {
                "result": {"percent": result.percent, "passed": result.passed},
                "enrollment": EnrollmentSerializer(enrollment).data,
            }
        )


class SubmissionViewSet(mixins.ListModelMixin, viewsets.GenericViewSet[Submission]):
    """Отправка и просмотр ответов на практические задания."""

    serializer_class = SubmissionSerializer
    permission_classes = [IsAuthenticatedUser]

    def get_queryset(self):  # type: ignore[no-untyped-def]
        """Вернуть только ответы текущего сотрудника."""
        employee = _current_employee(self.request)
        return Submission.objects.filter(employee=employee).select_related("task")

    def create(self, request: Request) -> Response:
        """Создать или повторно отправить ответ текущего сотрудника."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = get_object_or_404(PracticalTask, pk=serializer.validated_data["task"].pk)
        submission = submit_practical_task(
            task=task,
            employee=_current_employee(request),
            answer_text=serializer.validated_data.get("answer_text", ""),
            attachment=serializer.validated_data.get("attachment"),
        )
        return Response(self.get_serializer(submission).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="review-queue")
    def review_queue(self, request: Request) -> Response:
        """Вернуть очередь, доступную текущему куратору."""
        queryset = get_review_queue(_current_employee(request)).select_related("task", "employee")
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(queryset, many=True).data)

    @action(detail=True, methods=["post"])
    def review(self, request: Request, pk: str | None = None) -> Response:
        """Сохранить результат проверки разрешённым куратором."""
        submission = get_object_or_404(
            Submission.objects.select_related("task__reviewer", "employee__user"),
            pk=pk,
        )
        serializer = TaskReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            review = review_submission(
                submission,
                reviewer=_current_employee(request),
                **serializer.validated_data,
            )
        except ReviewNotAllowed as error:
            raise PermissionDenied(str(error)) from error
        except ReviewAlreadyCompleted as error:
            raise ValidationError(str(error)) from error
        return Response(TaskReviewSerializer(review).data)

    @action(detail=True, methods=["get"])
    def attachment(self, request: Request, pk: str | None = None) -> FileResponse:
        """Скачать вложение только автору ответа или разрешённому куратору."""
        submission = get_object_or_404(
            Submission.objects.select_related("task__reviewer", "employee__user"),
            pk=pk,
        )
        employee = _current_employee(request)
        if submission.employee_id != employee.id and not can_review_submission(
            employee, submission
        ):
            raise PermissionDenied("Нет доступа к вложению ответа.")
        if not submission.attachment:
            raise NotFound("Вложение отсутствует.")
        submission.attachment.open("rb")
        return FileResponse(
            submission.attachment,
            as_attachment=True,
            filename=Path(submission.attachment.name).name,
        )
