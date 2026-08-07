/**
 * Тест StatusBadge (issue #17, BRANDBOOK §6.8).
 *
 * Контракт: категория цвета бейджа зависит от статуса.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusBadge } from "./StatusBadge";

describe("StatusBadge", () => {
  it("рендерит лейбл статуса", () => {
    render(<StatusBadge status="created" label="Создан" />);
    expect(screen.getByText("Создан")).toBeInTheDocument();
  });

  it("создан → нейтральный класс", () => {
    const { container } = render(<StatusBadge status="created" label="Создан" />);
    expect(container.querySelector(".vektor-status-badge--neutral")).not.toBeNull();
  });

  it("in_progress → primary класс", () => {
    const { container } = render(<StatusBadge status="in_progress" label="Идёт оценка" />);
    expect(container.querySelector(".vektor-status-badge--primary")).not.toBeNull();
  });

  it("aggregated → accent класс", () => {
    const { container } = render(<StatusBadge status="aggregated" label="Результаты рассчитаны" />);
    expect(container.querySelector(".vektor-status-badge--accent")).not.toBeNull();
  });
});
