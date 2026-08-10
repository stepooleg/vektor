/**
 * Тесты App-shell (issue #2, #16): маршрутизация входа и защищённого приложения.
 *
 * Контракт: без аутентификации → LoginPage (форма входа);
 * с аутентифицированным пользователем → AppLayout (шапка, меню, тема).
 */
import { App as AntdApp } from "antd";
import { render, screen } from "@testing-library/react";
import type * as RouterDom from "react-router-dom";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { App, ProtectedRoutes } from "./App";
import { AuthProvider } from "./auth";
import { AuthContext, type AuthContextValue } from "./auth-context";
import { ThemeMode } from "./theme";

// Мокаем react-router-dom, чтобы не падать на BrowserRouter в jsdom.
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof RouterDom>("react-router-dom");
  return { ...actual };
});

vi.mock("@/api/feedback", () => ({
  getPraises: vi.fn().mockResolvedValue([]),
  getPortfolioEntries: vi.fn().mockResolvedValue([]),
  PORTFOLIO_TYPE_LABELS: {},
}));

vi.mock("@/api/auth", () => ({
  getCurrentUser: vi.fn(async () => {
    throw new Error("Нет сессии");
  }),
  login: vi.fn(),
  logout: vi.fn(),
}));

describe("App-shell", () => {
  it("без входа показывает страницу логина", async () => {
    render(<App />);

    // На странице входа есть заголовок и поле email.
    expect(await screen.findByText(/Вход в Vektor/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
  });

  it("без входа НЕ показывает защищённую навигацию", async () => {
    render(<App />);

    await screen.findByText(/Вход в Vektor/i);

    // Нет ссылок навигации защищённой части (Дашборд/Оценка/...).
    const navLinks = screen.queryAllByRole("link");
    const navTexts = navLinks.map((l) => (l.textContent ?? "").trim());
    expect(navTexts).not.toContain("Дашборд");
  });

  it("маршрут /portfolio открывает журнал достижений", async () => {
    render(
      <AntdApp>
        <AuthProvider>
          <MemoryRouter
            initialEntries={["/portfolio"]}
            future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
          >
            <ProtectedRoutes themeMode={ThemeMode.System} onThemeChange={vi.fn()} />
          </MemoryRouter>
        </AuthProvider>
      </AntdApp>,
    );

    expect(
      await screen.findByRole("heading", { name: "Обратная связь и портфолио" }),
    ).toBeInTheDocument();
  });

  it("прямой переход сотрудника в административный раздел показывает 403", async () => {
    const authValue: AuthContextValue = {
      user: {
        email: "employee@corp.local",
        name: "Сотрудник",
        employeeId: 1,
        roles: ["employee"],
      },
      loading: false,
      error: null,
      setUser: vi.fn(),
      signIn: vi.fn(),
      signOut: vi.fn(),
    };
    render(
      <AntdApp>
        <AuthContext.Provider value={authValue}>
          <MemoryRouter
            initialEntries={["/analytics"]}
            future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
          >
            <ProtectedRoutes themeMode={ThemeMode.System} onThemeChange={vi.fn()} />
          </MemoryRouter>
        </AuthContext.Provider>
      </AntdApp>,
    );

    expect(await screen.findByText("Нет доступа")).toBeInTheDocument();
    expect(screen.getByText(/недоступен для вашей роли/i)).toBeInTheDocument();
  });
});
