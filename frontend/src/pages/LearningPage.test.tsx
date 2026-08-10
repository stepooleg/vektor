/** Интерактивные сценарии LMS (SPEC §14.3, issue #68). */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  completeLesson,
  enrollInCourse,
  getCourse,
  getCourseCategories,
  getCourses,
  getMyLearning,
  submitQuiz,
} from "@/api/lms";
import { LearningPage } from "./LearningPage";

vi.mock("@/api/lms", () => ({
  getCourses: vi.fn(),
  getCourse: vi.fn(),
  getCourseCategories: vi.fn(),
  getMyLearning: vi.fn(),
  enrollInCourse: vi.fn(),
  completeLesson: vi.fn(),
  submitQuiz: vi.fn(),
  ENROLLMENT_STATUS_LABELS: {
    not_started: "Не начат",
    in_progress: "В процессе",
    completed: "Пройдён",
  },
}));

const course = {
  id: 1,
  title: "Безопасная разработка",
  description: "Практический курс",
  category: null,
  status: "published",
  is_mandatory: false,
  pass_threshold: 100,
  created_at: "2026-08-10",
  lessons: [
    {
      id: 10,
      title: "Введение",
      type: "text" as const,
      order: 1,
      content: "Прочитайте правила.",
      pass_score: 80,
      max_attempts: 3,
      questions: [],
    },
  ],
};

const enrollment = {
  id: 5,
  course: {
    id: course.id,
    title: course.title,
    description: course.description,
    is_mandatory: false,
    pass_threshold: 100,
  },
  status: "in_progress",
  progress_percent: 50,
  enrolled_at: "2026-08-10",
  completed_at: null,
  lesson_progresses: [],
  certificate: null,
};

describe("LearningPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getCourses).mockResolvedValue([course]);
    vi.mocked(getCourse).mockResolvedValue(course);
    vi.mocked(getCourseCategories).mockResolvedValue([]);
    vi.mocked(getMyLearning).mockResolvedValue([]);
  });

  it("открывает программу курса и записывает сотрудника", async () => {
    vi.mocked(enrollInCourse).mockResolvedValue({ ...enrollment, progress_percent: 0 });
    const user = userEvent.setup();
    render(<LearningPage />);

    await user.click(await screen.findByRole("button", { name: "Открыть курс" }));
    expect(await screen.findByRole("heading", { name: course.title })).toBeInTheDocument();
    expect(screen.getByText("Введение")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Записаться на курс" }));

    await waitFor(() => expect(enrollInCourse).toHaveBeenCalledWith(course.id));
    expect(await screen.findByText("Вы записаны на курс")).toBeInTheDocument();
  });

  it("показывает личный прогресс и сертификат завершённого курса", async () => {
    vi.mocked(getMyLearning).mockResolvedValue([
      {
        ...enrollment,
        status: "completed",
        progress_percent: 100,
        completed_at: "2026-08-11",
        certificate: {
          code: "CERT-123",
          employee_full_name: "Иванов Иван",
          course_title: course.title,
          issued_at: "2026-08-11",
        },
      },
    ]);
    const user = userEvent.setup();
    render(<LearningPage />);

    await user.click(screen.getByRole("tab", { name: "Моё обучение" }));

    expect(await screen.findByText("100% завершено")).toBeInTheDocument();
    expect(screen.getByText("Сертификат CERT-123")).toBeInTheDocument();
  });

  it("отмечает текстовый урок пройденным", async () => {
    vi.mocked(getMyLearning).mockResolvedValue([enrollment]);
    vi.mocked(completeLesson).mockResolvedValue({ ...enrollment, progress_percent: 100 });
    const user = userEvent.setup();
    render(<LearningPage />);

    await user.click(await screen.findByRole("button", { name: "Открыть курс" }));
    await user.click(await screen.findByRole("button", { name: "Отметить пройденным" }));

    await waitFor(() => expect(completeLesson).toHaveBeenCalledWith(course.id, 10));
    expect(await screen.findByText("Прогресс сохранён")).toBeInTheDocument();
  });

  it("отправляет выбранный ответ теста и показывает результат", async () => {
    const quizCourse = {
      ...course,
      lessons: [
        {
          id: 20,
          title: "Проверка знаний",
          type: "quiz" as const,
          order: 1,
          content: "",
          pass_score: 100,
          max_attempts: 2,
          questions: [
            {
              id: 30,
              text: "Где хранить секреты?",
              type: "single" as const,
              order: 1,
              options: [
                { id: 40, text: "В env", order: 1 },
                { id: 41, text: "В Git", order: 2 },
              ],
            },
          ],
        },
      ],
    };
    vi.mocked(getCourse).mockResolvedValue(quizCourse);
    vi.mocked(getMyLearning).mockResolvedValue([enrollment]);
    vi.mocked(submitQuiz).mockResolvedValue({
      result: { percent: 100, passed: true },
      enrollment: { ...enrollment, progress_percent: 100, status: "completed" },
    });
    const user = userEvent.setup();
    render(<LearningPage />);

    await user.click(await screen.findByRole("button", { name: "Открыть курс" }));
    await user.click(await screen.findByRole("radio", { name: "В env" }));
    await user.click(screen.getByRole("button", { name: "Отправить ответы" }));

    await waitFor(() => expect(submitQuiz).toHaveBeenCalledWith(course.id, 20, { 30: [40] }));
    expect(await screen.findByText("Тест пройден: 100%")).toBeInTheDocument();
  });
});
