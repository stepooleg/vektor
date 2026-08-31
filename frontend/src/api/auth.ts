/**
 * API аутентификации (SPEC §10.2).
 *
 * Соответствует бэкенду: POST /api/v1/auth/login/, POST /api/v1/auth/logout/.
 */
import { apiClient, setCsrfToken } from "./client";

export interface LoginRequest {
  identifier: string;
  password: string;
}

export interface AuthUser {
  email: string;
  name: string;
  employeeId: number | null;
  roles: RoleCode[];
}

export type RoleCode = "employee" | "manager" | "hr" | "methodologist";

interface AuthUserResponse {
  email: string;
  name: string;
  employee_id: number | null;
  roles: RoleCode[];
}

interface LoginResponse {
  detail: string;
  user: AuthUserResponse;
  csrfToken: string;
}

interface CurrentUserResponse extends AuthUserResponse {
  csrfToken: string;
}

/** Войти по AD-имени или email + пароль (сессионная cookie). */
export async function login(payload: LoginRequest): Promise<AuthUser> {
  const { data } = await apiClient.post<LoginResponse>("/auth/login/", payload);
  setCsrfToken(data.csrfToken);
  return toAuthUser(data.user);
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
  return toAuthUser(data);
}

function toAuthUser(data: AuthUserResponse): AuthUser {
  return {
    email: data.email,
    name: data.name,
    employeeId: data.employee_id,
    roles: data.roles,
  };
}
