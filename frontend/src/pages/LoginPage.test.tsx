/**
 * Тест страницы входа (issue #16).
 *
 * Контракт: форма рендерится, валидирует пустые поля,
 * вызывает signIn при сабмите. API-вызовы мокаются.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import type { ApiError } from "@/api/client";
import { AuthContext, type AuthContextValue } from "@/app/auth-context";
import { LoginPage } from "./LoginPage";
import { getLoginErrorMessage } from "./login-error";

// Мок API-входа: по умолчанию успех, можно переключить на отказ.
vi.mock("@/api/auth", () => ({
  getCurrentUser: vi.fn(async () => {
    throw new Error("Нет сессии");
  }),
  login: vi.fn(async ({ email }: { email: string }) => ({
    email,
    name: "Тестовый пользователь",
  })),
}));

describe("LoginPage", () => {
  const authValue: AuthContextValue = {
    user: null,
    loading: false,
    error: null,
    setUser: vi.fn(),
    signIn: vi.fn(),
    signOut: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("рендерит форму с полем учётной записи и кнопкой входа", () => {
    render(
      <AuthContext.Provider value={authValue}>
        <LoginPage />
      </AuthContext.Provider>,
    );

    expect(screen.getByLabelText(/учётная запись/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /войти/i })).toBeInTheDocument();
  });

  it("требует заполнения учётной записи и пароля (валидация)", async () => {
    render(
      <AuthContext.Provider value={authValue}>
        <LoginPage />
      </AuthContext.Provider>,
    );

    fireEvent.click(screen.getByRole("button", { name: /войти/i }));

    await waitFor(() => {
      expect(screen.getByText(/введите учётную запись или email/i)).toBeInTheDocument();
      expect(screen.getByText(/введите пароль/i)).toBeInTheDocument();
    });
  });

  it("принимает sAMAccountName для корпоративного LDAP-входа", async () => {
    render(
      <AuthContext.Provider value={authValue}>
        <LoginPage />
      </AuthContext.Provider>,
    );

    fireEvent.change(screen.getByLabelText(/корпоративная учётная запись/i), {
      target: { value: "a.ivanova" },
    });
    fireEvent.change(screen.getByLabelText(/пароль/i), {
      target: { value: "Strong-Pwd-12345" },
    });
    fireEvent.click(screen.getByRole("button", { name: /войти/i }));

    await waitFor(() => {
      expect(authValue.signIn).toHaveBeenCalledWith("a.ivanova", "Strong-Pwd-12345");
    });
  });

  it.each([
    [{ status: 401, detail: "Unauthorized" }, "Неверный email или пароль"],
    [{ status: 429, detail: "Locked" }, "Слишком много попыток входа"],
    [{ status: 0, detail: "Network Error" }, "Не удалось связаться с сервисом"],
    [{ status: 503, detail: "Service Unavailable" }, "Сервис временно недоступен"],
  ] satisfies Array<[ApiError, string]>)(
    "показывает безопасное сообщение для статуса $0.status",
    (error, expected) => {
      expect(getLoginErrorMessage(error)).toContain(expected);
    },
  );
});
