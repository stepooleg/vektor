/**
 * Тест App-shell (issue #2): рендерится без ошибок, показывает логотип,
 * боковое меню и переключатель темы.
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { App } from "./App";

describe("App-shell", () => {
  it("рендерится без ошибок и показывает название продукта", () => {
    render(<App />);

    expect(screen.getByText(/Vektor/i)).toBeInTheDocument();
  });

  it("содержит боковое меню с ключевыми разделами (SPEC §14)", () => {
    render(<App />);

    // Разделы навигации по SPEC §14 / BRANDBOOK §6.7. Ищем как ссылки (меню),
    // чтобы не пересекаться с заголовком страницы-заглушки.
    const navLinks = screen.getAllByRole("link");
    const navTexts = navLinks.map((l) => l.textContent ?? "");
    expect(navTexts).toEqual(expect.arrayContaining(["Дашборд", "Оценка", "Обучение"]));
  });

  it("содержит переключатель темы", () => {
    render(<App />);

    // Переключатель темы помечен aria-label для доступности.
    expect(screen.getByLabelText(/Тема/i)).toBeInTheDocument();
  });
});
