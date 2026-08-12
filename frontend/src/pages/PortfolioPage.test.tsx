/** Сценарии портфолио сотрудника (SPEC §6.2, issue #69). */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createPortfolioEntry, getPortfolioEntries, getPortfolioTargets } from "@/api/feedback";
import { PortfolioPage } from "./PortfolioPage";

vi.mock("@/api/feedback", () => ({
  getPortfolioEntries: vi.fn(),
  getPortfolioTargets: vi.fn(),
  createPortfolioEntry: vi.fn(),
  PORTFOLIO_TYPE_LABELS: { achievement: "Достижение", project: "Проект" },
}));

describe("PortfolioPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getPortfolioEntries).mockResolvedValue([]);
    vi.mocked(getPortfolioTargets).mockResolvedValue([
      { id: 1, full_name: "Пётр Смирнов", department: "Разработка", is_self: true },
    ]);
  });

  it("добавляет достижение и показывает его в ленте", async () => {
    vi.mocked(createPortfolioEntry).mockResolvedValue({
      id: 20,
      employee_name: "Пётр Смирнов",
      type: "achievement",
      title: "Запустил проект",
      description: "Точно в срок",
      created_at: "2026-08-12",
    });
    const user = userEvent.setup();
    render(<PortfolioPage />);

    await user.click(await screen.findByRole("button", { name: "Добавить достижение" }));
    await user.type(screen.getByLabelText("Название"), "Запустил проект");
    await user.type(screen.getByLabelText("Описание"), "Точно в срок");
    await user.click(screen.getByRole("button", { name: "Добавить" }));

    await waitFor(() =>
      expect(createPortfolioEntry).toHaveBeenCalledWith({
        employee: 1,
        type: "achievement",
        title: "Запустил проект",
        description: "Точно в срок",
      }),
    );
    expect(await screen.findByText("Достижение добавлено")).toBeInTheDocument();
    expect(screen.getByText("Запустил проект")).toBeInTheDocument();
  });
});
