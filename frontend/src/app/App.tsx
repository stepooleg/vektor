/**
 * Корневой компонент приложения Vektor.
 *
 * Связывает провайдеры (тема, AntD ConfigProvider, аутентификация), роутер,
 * защищённые маршруты (AppLayout). Все цвета — только дизайн-токены (§10.2).
 */
import { ConfigProvider, App as AntdApp, Result, Spin } from "antd";
import ruRU from "antd/locale/ru_RU";
import { lazy, Suspense, useMemo } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { LoginPage } from "@/pages/LoginPage";
import type { RoleCode } from "@/api/auth";
import { buildAntdConfig } from "./antdTheme";
import { AppLayout } from "./AppLayout";
import { AuthProvider } from "./auth";
import { useAuth } from "./auth-context";
import { ThemeMode, useTheme } from "./theme";

const DashboardPage = lazy(() =>
  import("@/pages/DashboardPage").then((module) => ({ default: module.DashboardPage })),
);
const AssessmentPage = lazy(() =>
  import("@/pages/AssessmentPage").then((module) => ({ default: module.AssessmentPage })),
);
const CompetenciesPage = lazy(() =>
  import("@/pages/CompetenciesPage").then((module) => ({ default: module.CompetenciesPage })),
);
const LearningPage = lazy(() =>
  import("@/pages/LearningPage").then((module) => ({ default: module.LearningPage })),
);
const IdpPage = lazy(() =>
  import("@/pages/IdpPage").then((module) => ({ default: module.IdpPage })),
);
const FeedbackPage = lazy(() =>
  import("@/pages/FeedbackPage").then((module) => ({ default: module.FeedbackPage })),
);
const AnalyticsPage = lazy(() =>
  import("@/pages/AnalyticsPage").then((module) => ({ default: module.AnalyticsPage })),
);

interface ProtectedRoutesProps {
  themeMode: ThemeMode;
  onThemeChange: (mode: ThemeMode) => void;
}

function RequireRoles({
  allowed,
  children,
}: {
  allowed: RoleCode[];
  children: React.ReactNode;
}): React.JSX.Element {
  const { user } = useAuth();
  const hasAccess = allowed.some((role) => user?.roles.includes(role));
  if (!hasAccess) {
    return (
      <Result status="403" title="Нет доступа" subTitle="Этот раздел недоступен для вашей роли." />
    );
  }
  return <>{children}</>;
}

/** Защищённые маршруты приложения (после входа). */
export function ProtectedRoutes({
  themeMode,
  onThemeChange,
}: ProtectedRoutesProps): React.JSX.Element {
  return (
    <Suspense fallback={<Spin size="large" aria-label="Загрузка раздела" />}>
      <Routes>
        <Route element={<AppLayout themeMode={themeMode} onThemeChange={onThemeChange} />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/assessment" element={<AssessmentPage />} />
          <Route
            path="/competencies"
            element={
              <RequireRoles allowed={["hr", "methodologist"]}>
                <CompetenciesPage />
              </RequireRoles>
            }
          />
          <Route path="/learning" element={<LearningPage />} />
          <Route path="/idp" element={<IdpPage />} />
          <Route path="/portfolio" element={<FeedbackPage />} />
          <Route path="/feedback" element={<FeedbackPage />} />
          <Route
            path="/analytics"
            element={
              <RequireRoles allowed={["hr", "manager"]}>
                <AnalyticsPage />
              </RequireRoles>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </Suspense>
  );
}

/** Решает, что показать: страницу входа или защищённое приложение. */
function Root(): React.JSX.Element {
  const { user, loading } = useAuth();
  const { mode, resolved, setMode } = useTheme();
  const antdConfig = useMemo(() => buildAntdConfig(resolved === ThemeMode.Dark), [resolved]);

  return (
    <ConfigProvider theme={antdConfig} locale={ruRU}>
      <AntdApp>
        <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          {loading ? (
            <div
              style={{
                minHeight: "100vh",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Spin size="large" aria-label="Загрузка сессии" />
            </div>
          ) : user ? (
            <ProtectedRoutes themeMode={mode} onThemeChange={setMode} />
          ) : (
            <LoginPage />
          )}
        </BrowserRouter>
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
