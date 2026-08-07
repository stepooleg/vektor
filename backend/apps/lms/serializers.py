"""Сериалайзеры LMS — каталог курсов (SPEC §7.1, §7.3)."""

from __future__ import annotations

from rest_framework import serializers

from apps.competencies.models import Competency

from .models import Category, Course, CourseCompetencyLink


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
        ]
        read_only_fields = ["created_at"]
