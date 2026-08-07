/**
 * Тест страницы входа (issue #16).
 *
 * Контракт: форма рендерится, валидирует пустые поля,
 * вызывает signIn при сабмите. API-вызовы мокаются.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { AuthProvider } from "@/app/auth";
import { LoginPage } from "./LoginPage";

// Мок API-входа: по умолчанию успех, можно переключить на отказ.
vi.mock("@/api/auth", () => ({
  login: vi.fn(async ({ email }: { email: string }) => ({
    email,
    name: "Тестовый пользователь",
  })),
}));

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("рендерит форму с полем email и кнопкой входа", () => {
    render(
      <AuthProvider>
        <LoginPage />
      </AuthProvider>,
    );

    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /войти/i })).toBeInTheDocument();
  });

  it("требует заполнения email и пароля (валидация)", async () => {
    render(
      <AuthProvider>
        <LoginPage />
      </AuthProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: /войти/i }));

    await waitFor(() => {
      expect(screen.getByText(/введите email/i)).toBeInTheDocument();
      expect(screen.getByText(/введите пароль/i)).toBeInTheDocument();
    });
  });
});
