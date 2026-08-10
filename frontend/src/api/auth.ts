/**
 * API аутентификации (SPEC §10.2).
 *
 * Соответствует бэкенду: POST /api/v1/auth/login/, POST /api/v1/auth/logout/.
 */
import { apiClient, setCsrfToken } from "./client";

export interface LoginRequest {
  email: string;
  password: string;
}

export interface AuthUser {
  email: string;
  name: string;
}

interface LoginResponse {
  detail: string;
  user: AuthUser;
  csrfToken: string;
}

interface CurrentUserResponse extends AuthUser {
  csrfToken: string;
}

/** Войти по email + пароль (сессионная cookie). */
export async function login(payload: LoginRequest): Promise<AuthUser> {
  const { data } = await apiClient.post<LoginResponse>("/auth/login/", payload);
  setCsrfToken(data.csrfToken);
  return data.user;
}

/** Завершить сессию. */
export async function logout(): Promise<void> {
  await apiClient.post("/auth/logout/", undefined, {
    headers: {
      "X-CSRFToken": apiClient.defaults.headers.common["X-CSRFToken"],
    },
  });
}

/** Получить пользователя действующей серверной сессии. */
export async function getCurrentUser(): Promise<AuthUser> {
  const { data } = await apiClient.get<CurrentUserResponse>("/auth/me/");
  setCsrfToken(data.csrfToken);
  return { email: data.email, name: data.name };
}
