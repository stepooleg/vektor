/** Интеграционный тест синхронизации CSS- и Ant Design-темы (issue #64). */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

const { buildAntdConfigMock } = vi.hoisted(() => ({
  buildAntdConfigMock: vi.fn(() => ({})),
}));

vi.mock("./antdTheme", () => ({
  buildAntdConfig: buildAntdConfigMock,
}));

vi.mock("@/api/auth", () => ({
  getCurrentUser: vi.fn(async () => ({
    email: "employee@corp.local",
    name: "Тестовый пользователь",
  })),
  login: vi.fn(),
  logout: vi.fn(),
}));

vi.mock("@/api/analytics", () => ({
  getEmployeeDashboard: vi.fn(async () => ({
    employee: {
      id: 1,
      full_name: "Тестовый пользователь",
      department: "Отдел",
      position: "Должность",
    },
    competency_profile: [],
    cycle_dynamics: [],
  })),
}));

describe("App theme", () => {
  beforeEach(() => {
    localStorage.clear();
    buildAntdConfigMock.mockClear();
  });

  it("перестраивает Ant Design-конфигурацию при выборе тёмной темы", async () => {
    render(<App />);
    await screen.findByRole("heading", { name: "Дашборд сотрудника" });

    fireEvent.click(screen.getByText("Тёмная", { exact: true }));

    await waitFor(() => {
      expect(buildAntdConfigMock).toHaveBeenLastCalledWith(true);
    });
  });
});
