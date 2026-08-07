/**
 * Тесты App-shell (issue #2, #16): маршрутизация входа и защищённого приложения.
 *
 * Контракт: без аутентификации → LoginPage (форма входа);
 * с аутентифицированным пользователем → AppLayout (шапка, меню, тема).
 */
import { render, screen } from "@testing-library/react";
import type * as RouterDom from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";

// Мокаем react-router-dom, чтобы не падать на BrowserRouter в jsdom.
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof RouterDom>("react-router-dom");
  return { ...actual };
});

describe("App-shell", () => {
  it("без входа показывает страницу логина", () => {
    render(<App />);

    // На странице входа есть заголовок и поле email.
    expect(screen.getByText(/Вход в Vektor/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
  });

  it("без входа НЕ показывает защищённую навигацию", () => {
    render(<App />);

    // Нет ссылок навигации защищённой части (Дашборд/Оценка/...).
    const navLinks = screen.queryAllByRole("link");
    const navTexts = navLinks.map((l) => (l.textContent ?? "").trim());
    expect(navTexts).not.toContain("Дашборд");
  });
});
