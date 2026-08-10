import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getEmployeeDashboard } from "@/api/analytics";
import { DashboardPage } from "./DashboardPage";

const authState = vi.hoisted(() => ({
  user: {
    email: "employee@corp.local",
    name: "Сотрудник",
    employeeId: 42 as number | null,
    roles: ["employee"],
  },
}));

vi.mock("@/app/auth-context", () => ({ useAuth: () => ({ user: authState.user }) }));
vi.mock("@/api/analytics", () => ({ getEmployeeDashboard: vi.fn() }));

describe("DashboardPage employee context", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authState.user.employeeId = 42;
    vi.mocked(getEmployeeDashboard).mockResolvedValue({
      employee: { id: 42, full_name: "Сотрудник", department: "Отдел", position: "Инженер" },
      competency_profile: [],
      cycle_dynamics: [],
    });
  });

  it("загружает дашборд текущего сотрудника без ручного ID", async () => {
    render(<DashboardPage />);

    await waitFor(() => expect(getEmployeeDashboard).toHaveBeenCalledWith(42));
    expect(screen.queryByText("ID сотрудника:")).not.toBeInTheDocument();
  });

  it("показывает понятное состояние без привязанного сотрудника", () => {
    authState.user.employeeId = null;
    render(<DashboardPage />);

    expect(screen.getByText(/профиль сотрудника не привязан/i)).toBeInTheDocument();
    expect(getEmployeeDashboard).not.toHaveBeenCalled();
  });

  it("показывает отдельное состояние при запрете доступа", async () => {
    vi.mocked(getEmployeeDashboard).mockRejectedValueOnce({
      isAxiosError: true,
      message: "Request failed with status code 403",
      response: { status: 403, data: { detail: "Внутренняя формулировка" } },
    });

    render(<DashboardPage />);

    expect(await screen.findByText(/у вас нет доступа к дашборду/i)).toBeInTheDocument();
  });
});
