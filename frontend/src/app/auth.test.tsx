/** Тесты восстановления серверной сессии в AuthProvider (issue #62). */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import * as authApi from "@/api/auth";
import { AuthProvider } from "./auth";
import { useAuth } from "./auth-context";

vi.mock("@/api/auth", () => ({
  getCurrentUser: vi.fn(async () => ({
    email: "alice@corp.local",
    name: "Алиса",
  })),
  login: vi.fn(),
  logout: vi.fn(),
}));

function AuthProbe(): React.JSX.Element {
  const { user, loading, signOut } = useAuth();
  return (
    <div>
      <span>{loading ? "Загрузка" : (user?.email ?? "Аноним")}</span>
      <button type="button" onClick={() => void signOut().catch(() => undefined)}>
        Выйти
      </button>
    </div>
  );
}

describe("AuthProvider", () => {
  it("восстанавливает пользователя из действующей серверной сессии", async () => {
    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>,
    );

    expect(await screen.findByText("alice@corp.local")).toBeInTheDocument();
  });

  it("не скрывает пользователя, если сервер не завершил сессию", async () => {
    vi.mocked(authApi.logout).mockRejectedValueOnce(new Error("CSRF Failed"));
    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>,
    );
    await screen.findByText("alice@corp.local");

    fireEvent.click(screen.getByRole("button", { name: "Выйти" }));

    await waitFor(() => expect(authApi.logout).toHaveBeenCalled());
    expect(screen.getByText("alice@corp.local")).toBeInTheDocument();
  });
});
