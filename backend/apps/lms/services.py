"""Сервисы LMS — автопроверка тестов и перемешивание (SPEC §7.2).

- ``grade_quiz``: автопроверка ответов по single/multiple;
- ``check_attempt_allowed``: лимит попыток;
- ``shuffled_question_ids``: детерминированное перемешивание вопросов.

Сертификация — только статус «пройдён/не пройдён» (SPEC §7.4), без PDF.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .models import AnswerOption, Lesson, Question

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True)
class GradeResult:
    """Результат автопроверки теста."""

    percent: int
    passed: bool
    correct_count: int
    total_count: int


def grade_quiz(lesson: Lesson, answers: dict[int, list[int]]) -> GradeResult:
    """Проверить ответы теста и вернуть процент правильных.

    ``answers``: {question_id: [selected_option_id, ...]}.
    Засчитывается вопрос, где множество выбранных options полностью совпадает
    с множеством правильных (для multiple) или единственный правильный (single).
    """
    questions: Sequence[Question] = list(lesson.questions.all())
    total = len(questions)
    if total == 0:
        return GradeResult(percent=0, passed=False, correct_count=0, total_count=0)

    correct_map: dict[int, set[int]] = {
        q.id: set(q.options.filter(is_correct=True).values_list("id", flat=True)) for q in questions
    }
    correct_count = 0
    for q in questions:
        selected = set(answers.get(q.id, []))
        if selected and selected == correct_map[q.id]:
            correct_count += 1

    percent = int(round(correct_count / total * 100))
    return GradeResult(
        percent=percent,
        passed=percent >= lesson.pass_score,
        correct_count=correct_count,
        total_count=total,
    )


def check_attempt_allowed(lesson: Lesson, *, attempts_used: int) -> bool:
    """Разрешена ли новая попытка (лимит max_attempts, SPEC §7.2).

    ``max_attempts == 0`` трактуется как «без лимита».
    """
    if lesson.max_attempts == 0:
        return True
    return attempts_used < lesson.max_attempts


def shuffled_question_ids(lesson: Lesson, *, seed: int) -> list[int]:
    """Детерминированно перемешанные ID вопросов урока (SPEC §7.2).

    Одинаковый ``seed`` → одинаковый порядок (воспроизводимость при реране).
    """
    rng = random.Random(seed)
    ids = list(lesson.questions.values_list("id", flat=True))
    rng.shuffle(ids)
    return ids


def correct_option_ids(question: Question) -> set[int]:
    """Множество ID правильных вариантов вопроса (для UI/диагностики)."""
    return set(
        AnswerOption.objects.filter(question=question, is_correct=True).values_list("id", flat=True)
    )
