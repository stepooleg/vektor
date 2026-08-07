/**
 * Контекст аутентификации (типы и хук useAuth) — без JSX.
 *
 * Вынесен из auth.tsx, чтобы fast-refresh корректно работал (файл с компонентом
 * AuthProvider не должен экспортировать не-компоненты).
 */
import { createContext, useContext } from "react";

import type { AuthUser } from "@/api/auth";

export interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  error: string | null;
  setUser: (user: AuthUser | null) => void;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

/** Хук доступа к контексту аутентификации. */
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (ctx === undefined) {
    throw new Error("useAuth должен использоваться внутри <AuthProvider>");
  }
  return ctx;
}
