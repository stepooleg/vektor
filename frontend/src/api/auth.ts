/**
 * API аутентификации (SPEC §10.2).
 *
 * Соответствует бэкенду: POST /api/v1/auth/login/, POST /api/v1/auth/logout/.
 */
import { apiClient } from "./client";

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
}

/** Войти по email + пароль (сессионная cookie). */
export async function login(payload: LoginRequest): Promise<AuthUser> {
  const { data } = await apiClient.post<LoginResponse>("/auth/login/", payload);
  return data.user;
}

/** Завершить сессию. */
export async function logout(): Promise<void> {
  await apiClient.post("/auth/logout/");
}
