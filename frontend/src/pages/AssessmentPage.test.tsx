/**
 * Тест страницы модуля оценки (issue #17, SPEC §14.2).
 *
 * Контракт: список циклов с бейджами статусов; API мокаются.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  createCycle,
  getCycles,
  getMyAssignments,
  getSetupOptions,
  submitAssignment,
  type AssessmentCycle,
} from "@/api/assessment";
import { AssessmentPage } from "./AssessmentPage";

const authState = vi.hoisted(() => ({
  user: {
    email: "employee@corp.local",
    name: "Сотрудник",
    employeeId: 1,
    roles: ["employee"],
  },
}));

vi.mock("@/app/auth-context", () => ({ useAuth: () => ({ user: authState.user }) }));
vi.mock("@/api/assessment", () => ({
  getCycles: vi.fn(),
  getCycleResults: vi.fn(),
  getSetupOptions: vi.fn(),
  createCycle: vi.fn(),
  startCycle: vi.fn(),
  getMyAssignments: vi.fn(),
  submitAssignment: vi.fn(),
  CYCLE_STATUS_LABELS: { created: "Создан", aggregated: "Результаты рассчитаны" },
  GROUP_LABELS: { manager: "Руководитель", self: "Самооценка" },
}));

describe("AssessmentPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authState.user.roles = ["employee"];
    vi.mocked(getCycles).mockResolvedValue([]);
    vi.mocked(getMyAssignments).mockResolvedValue([]);
  });

  it("показывает заголовок и пустое состояние при отсутствии циклов", async () => {
    (getCycles as unknown as ReturnType<typeof vi.fn>).mockResolvedValue([]);
    render(<AssessmentPage />);

    expect(screen.getByText(/Оценка 360°/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/Нет назначенных оценок/i)).toBeInTheDocument();
    });
    expect(screen.queryByText("Циклы оценки")).not.toBeInTheDocument();
  });

  it("рендерит список циклов со статусами", async () => {
    authState.user.roles = ["hr"];
    const cycles: AssessmentCycle[] = [
      {
        id: 1,
        name: "Оценка 2026",
        status: "aggregated",
        anonymity_threshold: 3,
        start_date: null,
        deadline: "2026-08-20",
        created_at: "2026-08-01",
      },
    ];
    (getCycles as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(cycles);

    render(<AssessmentPage />);

    await waitFor(() => {
      expect(screen.getByText("Оценка 2026")).toBeInTheDocument();
      expect(screen.getByText("Результаты рассчитаны")).toBeInTheDocument();
    });
  });

  it("сотруднику показывает только его задания без управления циклами", async () => {
    vi.mocked(getMyAssignments).mockResolvedValue([
      {
        id: 7,
        cycle: 1,
        cycle_name: "Оценка команды",
        deadline: "2026-08-24",
        participant_name: "Иван Иванов",
        group: "manager",
        completed: false,
        competencies: [],
      },
    ]);

    render(<AssessmentPage />);

    expect(await screen.findByText("Оценка команды")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Пройти оценку" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Создать цикл" })).not.toBeInTheDocument();
  });

  it("руководителю показывает мастер и создаёт цикл для выбранной команды", async () => {
    authState.user.roles = ["manager"];
    vi.mocked(getSetupOptions).mockResolvedValue({
      frameworks: [{ id: 3, name: "Корпоративная модель" }],
      participants: [{ id: 11, full_name: "Иван Иванов", department: "Разработка" }],
    });
    vi.mocked(createCycle).mockResolvedValue({
      id: 9,
      name: "Оценка команды",
      status: "assigned",
      anonymity_threshold: 3,
      start_date: "2026-08-11",
      deadline: "2026-08-24",
      created_at: "2026-08-10",
      participants_count: 1,
    });
    const user = userEvent.setup();
    render(<AssessmentPage />);

    await user.click(await screen.findByRole("button", { name: "Создать цикл" }));
    expect(await screen.findByText("Мастер создания цикла")).toBeInTheDocument();
    expect(screen.getByText("Модель компетенций")).toBeInTheDocument();
    expect(screen.getByText("Участники")).toBeInTheDocument();
    expect(screen.getByText("Сроки")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Название цикла"), "Оценка команды");
    await user.click(screen.getByLabelText("Модель компетенций"));
    await user.click(await screen.findByText("Корпоративная модель"));
    await user.click(screen.getByLabelText("Участники"));
    await user.click(await screen.findByText(/Иван Иванов/));
    fireEvent.change(screen.getByLabelText("Дата начала"), { target: { value: "2026-08-11" } });
    fireEvent.change(screen.getByLabelText("Дедлайн"), { target: { value: "2026-08-24" } });
    await user.click(screen.getByRole("button", { name: "Создать" }));

    await waitFor(() =>
      expect(createCycle).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Оценка команды",
          framework: 3,
          participant_ids: [11],
        }),
      ),
    );
  });

  it("отправляет заполненный опросник и показывает подтверждение", async () => {
    vi.mocked(getMyAssignments).mockResolvedValue([
      {
        id: 7,
        cycle: 1,
        cycle_name: "Оценка команды",
        deadline: "2026-08-24",
        participant_name: "Иван Иванов",
        group: "manager",
        completed: false,
        competencies: [
          {
            id: 5,
            name: "Командная работа",
            description: "Работает в команде",
            min_value: 1,
            max_value: 5,
          },
        ],
      },
    ]);
    vi.mocked(submitAssignment).mockResolvedValue({ completed: true });
    const user = userEvent.setup();
    render(<AssessmentPage />);

    await user.click(await screen.findByRole("button", { name: "Пройти оценку" }));
    expect(screen.getByRole("heading", { name: "Командная работа" })).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: "4" }));
    await user.type(screen.getByLabelText("Общий комментарий"), "Хороший результат");
    await user.click(screen.getByRole("button", { name: "Отправить оценку" }));

    await waitFor(() =>
      expect(submitAssignment).toHaveBeenCalledWith(7, {
        responses: [{ competency_id: 5, score: 4, comment: "" }],
        general_comment: "Хороший результат",
      }),
    );
    expect(await screen.findByText("Оценка отправлена")).toBeInTheDocument();
  });
});
