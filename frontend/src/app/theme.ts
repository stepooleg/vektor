/**
 * Логика темы Vektor (без JSX) — BRANDBOOK §8.1.
 *
 * Хук и константы живут здесь, чтобы файл `theme.tsx` экспортировал только
 * компонент (требование react-refresh/fast-refresh).
 */
import { useCallback, useEffect, useState } from "react";

export const THEME_STORAGE_KEY = "vektor-theme";

export enum ThemeMode {
  System = "system",
  Light = "light",
  Dark = "dark",
}

/** Все валидные значения темы (для валидации значения из localStorage). */
const VALID_MODES = new Set<string>(Object.values(ThemeMode));

const prefersDarkMedia = (): MediaQueryList => window.matchMedia("(prefers-color-scheme: dark)");

/** Разрешает системную тему в конкретную через matchMedia. */
function resolveSystemTheme(): Exclude<ThemeMode, ThemeMode.System> {
  return prefersDarkMedia().matches ? ThemeMode.Dark : ThemeMode.Light;
}

/** Читает сохранённый выбор, валидирует; иначе — System. */
function readStoredMode(): ThemeMode {
  const raw = localStorage.getItem(THEME_STORAGE_KEY);
  if (raw && VALID_MODES.has(raw)) {
    return raw as ThemeMode;
  }
  return ThemeMode.System;
}

export interface UseThemeResult {
  /** Выбранный режим (system | light | dark). */
  mode: ThemeMode;
  /** Фактически применённая тема (light | dark). */
  resolved: Exclude<ThemeMode, ThemeMode.System>;
  /** Сменить режим. */
  setMode: (mode: ThemeMode) => void;
}

/**
 * Хук темы: управляет data-theme на <html>, синхронизируется с localStorage
 * и системными настройками.
 */
export function useTheme(): UseThemeResult {
  const [mode, setModeState] = useState<ThemeMode>(readStoredMode);

  // Фактическая тема с учётом системной.
  const resolved =
    mode === ThemeMode.System
      ? resolveSystemTheme()
      : (mode as Exclude<ThemeMode, ThemeMode.System>);

  // Применяем атрибут и реагируем на смену системной темы.
  useEffect(() => {
    document.documentElement.dataset.theme = resolved;
  }, [resolved]);

  // Подписка на изменения системной темы (когда режим — System).
  useEffect(() => {
    if (mode !== ThemeMode.System) {
      return;
    }
    const mql = prefersDarkMedia();
    const handler = (): void => {
      document.documentElement.dataset.theme = resolveSystemTheme();
    };
    mql.addEventListener("change", handler);
    return () => mql.removeEventListener("change", handler);
  }, [mode]);

  const setMode = useCallback((next: ThemeMode): void => {
    setModeState(next);
    localStorage.setItem(THEME_STORAGE_KEY, next);
  }, []);

  return { mode, resolved, setMode };
}
