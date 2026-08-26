/**
 * Провайдер аутентификации (текущий пользователь, login/logout).
 *
 * Контекст и хук useAuth вынесены в auth-context.ts (fast-refresh).
 */
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import { getCurrentUser, login, logout, type AuthUser } from "@/api/auth";
import { toApiError } from "@/api/client";
import { AuthContext, type AuthContextValue } from "./auth-context";

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps): React.JSX.Element {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    getCurrentUser()
      .then((currentUser) => {
        if (!cancelled) setUser(currentUser);
      })
      .catch(() => {
        if (!cancelled) setUser(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const signIn = useCallback(async (identifier: string, password: string) => {
    setLoading(true);
    setError(null);
    try {
      const u = await login({ identifier, password });
      setUser(u);
    } catch (e) {
      setError(toApiError(e).detail);
      throw e;
    } finally {
      setLoading(false);
    }
  }, []);

  const signOut = useCallback(async () => {
    setError(null);
    try {
      await logout();
      setUser(null);
    } catch (e) {
      setError(toApiError(e).detail);
      throw e;
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, loading, error, setUser, signIn, signOut }),
    [user, loading, error, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
