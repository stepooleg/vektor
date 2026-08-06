/**
 * Маппинг дизайн-токенов Vektor (BRANDBOOK §8.2) в тему Ant Design.
 *
 * AntD ConfigProvider принимает `theme.token`; мы выводим значения из
 * CSS-переменных, чтобы оставался единый источник правды (tokens.css),
 * и AntD-компоненты не расходились с брендом.
 *
 * BRANDBOOK §6.1: скругление компонентов — 8px; шрифт — Ubuntu.
 */
import { theme as antdTheme, type ThemeConfig } from "antd";

// Чтение CSS-переменной из вычисленного стиля :root.
function readVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/**
 * Конфигурация AntD-темы для выбранной темы (light/dark).
 *
 * Цвета берутся из CSS-переменных (зависят от атрибута `data-theme` на <html>),
 * поэтому при переключении темы достаточно перерендерить провайдер.
 */
export function buildAntdConfig(isDark: boolean): ThemeConfig {
  const algorithm = isDark ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm;

  // Fallback-значения соответствуют tokens.css (на случай SSR/раннего доступа).
  const primary = readVar("--color-primary") || (isDark ? "#5C7CFA" : "#3B5BDB");
  const accent = readVar("--color-accent") || (isDark ? "#20C997" : "#12B886");
  const success = readVar("--color-success") || accent;
  const warning = readVar("--color-warning") || (isDark ? "#FAB005" : "#F59F00");
  const error = readVar("--color-error") || (isDark ? "#FA5252" : "#E03131");

  return {
    algorithm,
    token: {
      fontFamily: "'Ubuntu', 'Roboto', system-ui, sans-serif",
      borderRadius: 8,
      borderRadiusLG: 12,
      wireframe: false,
      colorPrimary: primary,
      colorSuccess: success,
      colorWarning: warning,
      colorError: error,
      colorInfo: primary,
    },
    components: {
      Layout: {
        headerBg: "transparent",
        siderBg: "transparent",
      },
    },
  };
}
