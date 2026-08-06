/**
 * Провайдер темы Vektor (BRANDBOOK §8.1).
 *
 * Тонкая обёртка: вся логика — в `theme.ts`, здесь только компонент
 * (требование react-refresh/fast-refresh).
 */
import type { ReactNode } from "react";

import { useTheme } from "./theme";

interface ThemeProviderProps {
  children: ReactNode;
}

/**
 * Провайдер темы: инициализирует атрибут `data-theme` на <html> при первом
 * монтировании. Контекст добавим, когда потребуется разделять режим глубоко
 * по дереву без проп-дрilling.
 */
export function ThemeProvider({ children }: ThemeProviderProps): ReactNode {
  useTheme();
  return children;
}
