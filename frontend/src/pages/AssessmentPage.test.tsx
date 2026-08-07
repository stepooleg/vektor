/**
 * Тест страницы модуля оценки (issue #17, SPEC §14.2).
 *
 * Контракт: список циклов с бейджами статусов; API мокаются.
 */
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { getCycles, type AssessmentCycle } from "@/api/assessment";
import { AssessmentPage } from "./AssessmentPage";

vi.mock("@/api/assessment", () => ({
  getCycles: vi.fn(),
  getCycleResults: vi.fn(),
  CYCLE_STATUS_LABELS: { created: "Создан", aggregated: "Результаты рассчитаны" },
  GROUP_LABELS: { manager: "Руководитель" },
}));

describe("AssessmentPage", () => {
  it("показывает заголовок и пустое состояние при отсутствии циклов", async () => {
    (getCycles as unknown as ReturnType<typeof vi.fn>).mockResolvedValue([]);
    render(<AssessmentPage />);

    expect(screen.getByText(/Оценка 360°/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/Пока нет циклов/i)).toBeInTheDocument();
    });
  });

  it("рендерит список циклов со статусами", async () => {
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
});
