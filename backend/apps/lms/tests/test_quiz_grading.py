"""Тесты автопроверки тестов (Test-First, SPEC §7.2, issue #20).

Контракты:
- автопроверка по типам single/multiple (сравнение с правильными вариантами);
- учёт проходного балла и числа попыток;
- перемешивание вопросов детерминированно при фиксированном seed;
- scale-вопрос — правильный ответ в диапазоне.
"""

from __future__ import annotations

import pytest

from apps.lms.models import AnswerOption, Lesson, Question
from apps.lms.services import (
    check_attempt_allowed,
    grade_quiz,
    shuffled_question_ids,
)


def _make_quiz_with_questions() -> tuple[Lesson, list[Question]]:
    """Создать тест (quiz) с двумя single-вопросами."""
    from apps.lms.models import Course

    course = Course.objects.create(title="Курс")
    lesson = Lesson.objects.create(
        course=course,
        title="Тест",
        type=Lesson.Type.QUIZ.value,
        pass_score=50,
        max_attempts=3,
    )
    q1 = Question.objects.create(
        lesson=lesson, text="2+2?", type=Question.Type.SINGLE.value, order=1
    )
    AnswerOption.objects.create(question=q1, text="3", is_correct=False, order=1)
    AnswerOption.objects.create(question=q1, text="4", is_correct=True, order=2)
    q2 = Question.objects.create(
        lesson=lesson, text="Столица РФ?", type=Question.Type.SINGLE.value, order=2
    )
    AnswerOption.objects.create(question=q2, text="Москва", is_correct=True, order=1)
    AnswerOption.objects.create(question=q2, text="Питер", is_correct=False, order=2)
    return lesson, [q1, q2]


@pytest.mark.django_db
def test_grade_single_correct_all() -> None:
    """Все ответы верны → 100%, пройден."""
    lesson, [q1, q2] = _make_quiz_with_questions()
    # Ответы: option_id правильных.
    correct_opt1 = q1.options.get(is_correct=True)
    correct_opt2 = q2.options.get(is_correct=True)
    answers = {q1.id: [correct_opt1.id], q2.id: [correct_opt2.id]}

    result = grade_quiz(lesson, answers)

    assert result.percent == 100
    assert result.passed is True


@pytest.mark.django_db
def test_grade_single_half_correct() -> None:
    """Половина верна → 50%, пройден при pass_score=50."""
    lesson, [q1, q2] = _make_quiz_with_questions()
    correct_opt1 = q1.options.get(is_correct=True)
    wrong_opt2 = q2.options.get(is_correct=False)
    answers = {q1.id: [correct_opt1.id], q2.id: [wrong_opt2.id]}

    result = grade_quiz(lesson, answers)

    assert result.percent == 50
    assert result.passed is True  # pass_score=50


@pytest.mark.django_db
def test_grade_multiple_requires_all_correct() -> None:
    """Multiple: засчитывается только при всех правильных вариантах."""
    from apps.lms.models import Course

    course = Course.objects.create(title="Курс")
    lesson = Lesson.objects.create(
        course=course, title="Т", type=Lesson.Type.QUIZ.value, pass_score=100
    )
    q = Question.objects.create(
        lesson=lesson, text="Выберите чётные", type=Question.Type.MULTIPLE.value
    )
    opt2 = AnswerOption.objects.create(question=q, text="2", is_correct=True, order=1)
    opt3 = AnswerOption.objects.create(question=q, text="3", is_correct=False, order=2)
    opt4 = AnswerOption.objects.create(question=q, text="4", is_correct=True, order=3)

    # Выбраны только 2 и 4 (все правильные) → верно.
    result_ok = grade_quiz(lesson, {q.id: [opt2.id, opt4.id]})
    assert result_ok.percent == 100

    # Выбран 2 и 3 (один лишний) → неверно.
    result_partial = grade_quiz(lesson, {q.id: [opt2.id, opt3.id]})
    assert result_partial.percent == 0


@pytest.mark.django_db
def test_attempt_limit_enforced() -> None:
    """Превышение числа попыток блокирует новую попытку (SPEC §7.2)."""
    from apps.lms.models import Course

    course = Course.objects.create(title="Курс")
    lesson = Lesson.objects.create(
        course=course, title="Т", type=Lesson.Type.QUIZ.value, max_attempts=2
    )

    assert check_attempt_allowed(lesson, attempts_used=1) is True
    assert check_attempt_allowed(lesson, attempts_used=2) is False


@pytest.mark.django_db
def test_shuffle_deterministic_by_seed() -> None:
    """Перемешивание детерминированно при одинаковом seed (SPEC §7.2)."""
    from apps.lms.models import Course

    course = Course.objects.create(title="Курс")
    lesson = Lesson.objects.create(course=course, title="Т", type=Lesson.Type.QUIZ.value)
    ids = [
        Question.objects.create(
            lesson=lesson, text=f"Q{i}", type=Question.Type.SINGLE.value, order=i
        ).id
        for i in range(5)
    ]

    shuffled1 = shuffled_question_ids(lesson, seed=42)
    shuffled2 = shuffled_question_ids(lesson, seed=42)

    assert shuffled1 == shuffled2  # один seed → один порядок
    assert set(shuffled1) == set(ids)  # те же вопросы
    # Скорее всего порядок изменён (не равен исходному).
    assert shuffled1 != ids or len(ids) == 1
