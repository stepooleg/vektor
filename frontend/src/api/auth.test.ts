import { afterEach, describe, expect, it, vi } from "vitest";

import { getCurrentUser, login, logout } from "./auth";
import { apiClient } from "./client";

describe("auth API CSRF", () => {
  afterEach(() => vi.restoreAllMocks());

  it("сохраняет CSRF-токен после входа и передаёт его при выходе", async () => {
    const post = vi
      .spyOn(apiClient, "post")
      .mockResolvedValueOnce({
        data: {
          detail: "Вход выполнен.",
          user: { email: "alice@corp.local", name: "Алиса" },
          csrfToken: "login-token",
        },
      })
      .mockResolvedValueOnce({ data: { detail: "Сессия завершена." } });

    await login({ email: "alice@corp.local", password: "password" });
    await logout();

    expect(post).toHaveBeenLastCalledWith("/auth/logout/", undefined, {
      headers: { "X-CSRFToken": "login-token" },
    });
  });

  it("обновляет CSRF-токен при восстановлении серверной сессии", async () => {
    vi.spyOn(apiClient, "get").mockResolvedValueOnce({
      data: { email: "alice@corp.local", name: "Алиса", csrfToken: "restore-token" },
    });
    const post = vi.spyOn(apiClient, "post").mockResolvedValueOnce({ data: {} });

    await getCurrentUser();
    await logout();

    expect(post).toHaveBeenCalledWith("/auth/logout/", undefined, {
      headers: { "X-CSRFToken": "restore-token" },
    });
  });
});
