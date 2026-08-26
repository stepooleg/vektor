/** Интерактивные сценарии ИПР (SPEC §14.4, issue #73). */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  autoGeneratePlan,
  createDevelopmentPlan,
  getDevelopmentPlans,
  getIdpOptions,
  updateDevAction,
} from "@/api/idp";
import type * as IdpApi from "@/api/idp";
import { useAuth } from "@/app/auth-context";
import { IdpPage } from "./IdpPage";

vi.mock("@/api/idp", async (importOriginal) => {
  const actual = await importOriginal<typeof IdpApi>();
  return {
    ...actual,
    getDevelopmentPlans: vi.fn(),
    getIdpOptions: vi.fn(),
    createDevelopmentPlan: vi.fn(),
    autoGeneratePlan: vi.fn(),
    updateDevelopmentPlan: vi.fn(),
    createDevGoal: vi.fn(),
    deleteDevGoal: vi.fn(),
    createDevAction: vi.fn(),
    updateDevAction: vi.fn(),
    deleteDevAction: vi.fn(),
  };
});
vi.mock("@/app/auth-context", () => ({ useAuth: vi.fn() }));

const plan = {
  id: 1,
  employee: 2,
  employee_name: "Иванов Анна",
  title: "ИПР на полугодие",
  status: "in_progress",
  progress_percent: 25,
  goals: [
    {
      id: 10,
      plan: 1,
      title: "Развить лидерство",
      description: "",
      competency: 3,
      target_level: 4,
      source: {
        type: "assessment" as const,
        cycle_id: 7,
        cycle_name: "Оценка 2026",
        current_level: 2.5,
        expected_level: 4,
      },
      actions: [
        {
          id: 20,
          goal: 10,
          type: "practice",
          title: "Провести ретроспективу",
          status: "in_progress",
          progress_percent: 25,
          due_date: null,
          course: null,
          mentor: null,
        },
      ],
    },
  ],
};

describe("IdpPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getDevelopmentPlans).mockResolvedValue([plan]);
    vi.mocked(getIdpOptions).mockResolvedValue({
      employees: [{ id: 2, name: "Иванов Анна" }],
      cycles: [{ id: 7, name: "Оценка 2026" }],
      competencies: [{ id: 3, name: "Лидерство" }],
    });
    vi.mocked(useAuth).mockReturnValue({
      user: {
        email: "manager@corp.local",
        name: "Руководитель",
        employeeId: 1,
        roles: ["manager"],
      },
      loading: false,
      error: null,
      setUser: vi.fn(),
      signIn: vi.fn(),
      signOut: vi.fn(),
    });
  });

  it("показывает прогресс и объяснимый источник автоподбора", async () => {
    render(<IdpPage />);

    expect(await screen.findByText("25% выполнено")).toBeInTheDocument();
    expect(screen.getByText("Оценка 2026: 2.5 → 4")).toBeInTheDocument();
  });

  it("руководитель создаёт ручной план для подчинённого", async () => {
    vi.mocked(createDevelopmentPlan).mockResolvedValue({ ...plan, goals: [] });
    const user = userEvent.setup();
    render(<IdpPage />);

    await user.click(await screen.findByRole("button", { name: "Создать ИПР" }));
    await user.click(screen.getByRole("combobox", { name: "Сотрудник" }));
    const employeeOptions = await screen.findAllByText("Иванов Анна");
    await user.click(employeeOptions[employeeOptions.length - 1]);
    await user.type(screen.getByLabelText("Название"), "ИПР 2027");
    await user.click(screen.getByRole("button", { name: "Создать" }));

    await waitFor(() =>
      expect(createDevelopmentPlan).toHaveBeenCalledWith({
        employee: 2,
        title: "ИПР 2027",
      }),
    );
  });

  it("формирует план из выбранного цикла оценки", async () => {
    vi.mocked(autoGeneratePlan).mockResolvedValue(plan);
    const user = userEvent.setup();
    render(<IdpPage />);

    await user.click(await screen.findByRole("button", { name: "Автоподбор" }));
    await user.click(screen.getByRole("combobox", { name: "Сотрудник" }));
    const employeeOptions = await screen.findAllByText("Иванов Анна");
    await user.click(employeeOptions[employeeOptions.length - 1]);
    await user.click(screen.getByRole("combobox", { name: "Цикл оценки" }));
    const cycleOptions = await screen.findAllByText("Оценка 2026");
    await user.click(cycleOptions[cycleOptions.length - 1]);
    await user.click(screen.getByRole("button", { name: "Сформировать" }));

    await waitFor(() => expect(autoGeneratePlan).toHaveBeenCalledWith(2, 7));
  });

  it("сохраняет прогресс действия", async () => {
    vi.mocked(updateDevAction).mockResolvedValue({
      ...plan.goals[0].actions[0],
      progress_percent: 50,
    });
    const user = userEvent.setup();
    render(<IdpPage />);

    await user.click(
      await screen.findByRole("combobox", { name: "Прогресс: Провести ретроспективу" }),
    );
    await user.click(await screen.findByText("50%"));

    await waitFor(() => expect(updateDevAction).toHaveBeenCalledWith(20, { progress_percent: 50 }));
  });
});
