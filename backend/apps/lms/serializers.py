"""Сериалайзеры LMS — каталог курсов (SPEC §7.1, §7.3)."""

from __future__ import annotations

from rest_framework import serializers

from apps.competencies.models import Competency

from .models import (
    AnswerOption,
    Category,
    Certificate,
    Course,
    CourseCompetencyLink,
    Enrollment,
    Lesson,
    LessonProgress,
    Question,
)


class AnswerOptionSerializer(serializers.ModelSerializer[AnswerOption]):
    """Безопасное представление варианта без признака правильности."""

    class Meta:
        model = AnswerOption
        fields = ["id", "text", "order"]


class QuestionSerializer(serializers.ModelSerializer[Question]):
    """Вопрос теста для слушателя."""

    options = AnswerOptionSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ["id", "text", "type", "order", "options"]


class LessonSerializer(serializers.ModelSerializer[Lesson]):
    """Материал программы курса."""

    questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Lesson
        fields = [
            "id",
            "title",
            "type",
            "order",
            "content",
            "pass_score",
            "max_attempts",
            "questions",
        ]


class CategorySerializer(serializers.ModelSerializer[Category]):
    """Сериалайзер категории каталога."""

    class Meta:
        """Метаданные сериалайзера категории."""

        model = Category
        fields = ["id", "name", "parent"]


class CourseCompetencyLinkSerializer(serializers.ModelSerializer[CourseCompetencyLink]):
    """Сериалайзер привязки курса к компетенции."""

    competency_name = serializers.CharField(source="competency.name", read_only=True)

    class Meta:
        """Метаданные сериалайзера привязки."""

        model = CourseCompetencyLink
        fields = ["id", "course", "competency", "competency_name"]


class CourseSerializer(serializers.ModelSerializer[Course]):
    """Сериалайзер курса."""

    competencies = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Competency.objects.all(),
        source="competency_links.competency",
        write_only=True,
        required=False,
    )
    lessons = LessonSerializer(many=True, read_only=True)

    class Meta:
        """Метаданные сериалайзера курса."""

        model = Course
        fields = [
            "id",
            "title",
            "description",
            "category",
            "status",
            "is_mandatory",
            "pass_threshold",
            "created_at",
            "competencies",
            "lessons",
        ]
        read_only_fields = ["created_at"]


class CourseSummarySerializer(serializers.ModelSerializer[Course]):
    """Краткие данные курса для личного кабинета."""

    class Meta:
        model = Course
        fields = ["id", "title", "description", "is_mandatory", "pass_threshold"]


class LessonProgressSerializer(serializers.ModelSerializer[LessonProgress]):
    """Статус прохождения отдельного урока."""

    class Meta:
        model = LessonProgress
        fields = ["lesson", "completed", "best_score", "attempts_used"]


class CertificateSerializer(serializers.ModelSerializer[Certificate]):
    """Статус-сертификат завершённого курса."""

    class Meta:
        model = Certificate
        fields = ["code", "employee_full_name", "course_title", "issued_at"]


class EnrollmentSerializer(serializers.ModelSerializer[Enrollment]):
    """Запись на курс с прогрессом и сертификатом."""

    course = CourseSummarySerializer(read_only=True)
    lesson_progresses = LessonProgressSerializer(many=True, read_only=True)
    certificate = CertificateSerializer(read_only=True)

    class Meta:
        model = Enrollment
        fields = [
            "id",
            "course",
            "status",
            "progress_percent",
            "enrolled_at",
            "completed_at",
            "lesson_progresses",
            "certificate",
        ]
