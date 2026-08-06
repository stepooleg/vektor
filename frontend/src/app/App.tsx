/**
 * Корневой компонент приложения Vektor (issue #2).
 *
 * Связывает провайдеры (тема, AntD ConfigProvider), роутер и AppLayout.
 * Все цвета — только через дизайн-токены (BRANDBOOK §10.2).
 */
import { ConfigProvider } from "antd";
import ruRU from "antd/locale/ru_RU";
import { useMemo } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { PlaceholderPage } from "@/pages/PlaceholderPage";
import { buildAntdConfig } from "./antdTheme";
import { AppLayout } from "./AppLayout";
import { ThemeMode, useTheme } from "./theme";

/** Маршруты каркаса (SPEC §14) — страницы-заглушки. */
const ROUTES = [
  {
    path: "/assessment",
    title: "Оценка",
    description: "Циклы оценки 360°, самооценка, результаты.",
  },
  {
    path: "/learning",
    title: "Обучение",
    description: "Каталог курсов, прохождение, личный кабинет.",
  },
  { path: "/idp", title: "ИПР", description: "Индивидуальный план развития и прогресс." },
  { path: "/portfolio", title: "Портфолио", description: "Журнал достижений сотрудника." },
  {
    path: "/feedback",
    title: "Обратная связь",
    description: "Благодарности и запрос обратной связи.",
  },
  {
    path: "/analytics",
    title: "Аналитика",
    description: "Дашборды по компании, сотрудникам, обучению.",
  },
] as const;

export function App(): React.JSX.Element {
  const { mode, resolved, setMode } = useTheme();

  // Пересобираем AntD-конфиг при смене фактической темы.
  const antdConfig = useMemo(() => buildAntdConfig(resolved === ThemeMode.Dark), [resolved]);

  return (
    <ConfigProvider theme={antdConfig} locale={ruRU}>
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout themeMode={mode} onThemeChange={setMode} />}>
            <Route
              path="/"
              element={
                <PlaceholderPage
                  title="Дашборд"
                  description="Сводка по оценке, обучению и развитию."
                />
              }
            />
            {ROUTES.map((route) => (
              <Route
                key={route.path}
                path={route.path}
                element={<PlaceholderPage title={route.title} description={route.description} />}
              />
            ))}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
}
