/**
 * Корневой компонент приложения Vektor.
 *
 * Связывает провайдеры (тема, AntD ConfigProvider, аутентификация), роутер,
 * защищённые маршруты (AppLayout). Все цвета — только дизайн-токены (§10.2).
 */
import { ConfigProvider, App as AntdApp } from "antd";
import ruRU from "antd/locale/ru_RU";
import { useMemo } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AssessmentPage } from "@/pages/AssessmentPage";
import { CompetenciesPage } from "@/pages/CompetenciesPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { LoginPage } from "@/pages/LoginPage";
import { PlaceholderPage } from "@/pages/PlaceholderPage";
import { buildAntdConfig } from "./antdTheme";
import { AppLayout } from "./AppLayout";
import { AuthProvider } from "./auth";
import { useAuth } from "./auth-context";
import { ThemeMode, useTheme } from "./theme";

/** Защищённые маршруты приложения (после входа). */
function ProtectedRoutes(): React.JSX.Element {
  const { mode, setMode } = useTheme();

  return (
    <Routes>
      <Route element={<AppLayout themeMode={mode} onThemeChange={setMode} />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/assessment" element={<AssessmentPage />} />
        <Route path="/competencies" element={<CompetenciesPage />} />
        <Route
          path="/learning"
          element={
            <PlaceholderPage
              title="Обучение"
              description="Каталог курсов, прохождение, личный кабинет."
            />
          }
        />
        <Route
          path="/idp"
          element={
            <PlaceholderPage title="ИПР" description="Индивидуальный план развития и прогресс." />
          }
        />
        <Route
          path="/portfolio"
          element={
            <PlaceholderPage title="Портфолио" description="Журнал достижений сотрудника." />
          }
        />
        <Route
          path="/feedback"
          element={
            <PlaceholderPage
              title="Обратная связь"
              description="Благодарности и запрос обратной связи."
            />
          }
        />
        <Route
          path="/analytics"
          element={
            <PlaceholderPage
              title="Аналитика"
              description="Дашборды по компании, сотрудникам, обучению."
            />
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

/** Решает, что показать: страницу входа или защищённое приложение. */
function Root(): React.JSX.Element {
  const { user } = useAuth();
  const { resolved } = useTheme();
  const antdConfig = useMemo(() => buildAntdConfig(resolved === ThemeMode.Dark), [resolved]);

  return (
    <ConfigProvider theme={antdConfig} locale={ruRU}>
      <AntdApp>
        <BrowserRouter>{user ? <ProtectedRoutes /> : <LoginPage />}</BrowserRouter>
      </AntdApp>
    </ConfigProvider>
  );
}

export function App(): React.JSX.Element {
  return (
    <AuthProvider>
      <Root />
    </AuthProvider>
  );
}
