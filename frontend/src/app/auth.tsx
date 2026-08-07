/**
 * Провайдер аутентификации (текущий пользователь, login/logout).
 *
 * Контекст и хук useAuth вынесены в auth-context.ts (fast-refresh).
 */
import { useCallback, useMemo, useState, type ReactNode } from "react";

import type { AuthUser } from "@/api/auth";
import { AuthContext, type AuthContextValue } from "./auth-context";

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps): React.JSX.Element {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Динамический импорт избегает циклической зависимости api/auth ↔ auth.
  const signIn = useCallback(async (email: string, password: string) => {
    setLoading(true);
    setError(null);
    try {
      const { login } = await import("@/api/auth");
      const u = await login({ email, password });
      setUser(u);
    } catch (e) {
      const { toApiError } = await import("@/api/client");
      setError(toApiError(e).detail);
      throw e;
    } finally {
      setLoading(false);
    }
  }, []);

  const signOut = useCallback(async () => {
    const { logout } = await import("@/api/auth");
    await logout().catch(() => {
      /* игнорируем ошибку сети при выходе — локально чистим всё равно */
    });
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, loading, error, setUser, signIn, signOut }),
    [user, loading, error, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
