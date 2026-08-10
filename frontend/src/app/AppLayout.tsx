/**
 * Главный layout приложения Vektor (BRANDBOOK §6.7, SPEC §14).
 *
 * Шапка: логотип, переключатель темы, аватар пользователя (заглушка).
 * Боковое меню: ключевые разделы по SPEC §14 (каркас, ссылки-заглушки).
 * Контент: маршрутизируемые страницы.
 */
import {
  BarChartOutlined,
  BookOutlined,
  CalendarOutlined,
  DashboardOutlined,
  FileTextOutlined,
  HeartOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  SolutionOutlined,
  TrophyOutlined,
} from "@ant-design/icons";
import { App, Avatar, Button, Dropdown, Layout, Menu, Segmented, Space } from "antd";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";

import { Logo } from "@/components/Logo";
import type { RoleCode } from "@/api/auth";
import { ThemeMode } from "./theme";
import { useAuth } from "./auth-context";

const { Header, Sider, Content } = Layout;

// Пункты навигации (SPEC §14).
const NAV_ITEMS: Array<{
  key: string;
  icon: React.JSX.Element;
  label: React.JSX.Element;
  allowedRoles?: RoleCode[];
}> = [
  { key: "/", icon: <DashboardOutlined />, label: <Link to="/">Дашборд</Link> },
  { key: "/assessment", icon: <CalendarOutlined />, label: <Link to="/assessment">Оценка</Link> },
  {
    key: "/competencies",
    icon: <TrophyOutlined />,
    label: <Link to="/competencies">Компетенции</Link>,
    allowedRoles: ["hr", "methodologist"],
  },
  { key: "/learning", icon: <BookOutlined />, label: <Link to="/learning">Обучение</Link> },
  { key: "/idp", icon: <SolutionOutlined />, label: <Link to="/idp">ИПР</Link> },
  { key: "/portfolio", icon: <FileTextOutlined />, label: <Link to="/portfolio">Портфолио</Link> },
  { key: "/feedback", icon: <HeartOutlined />, label: <Link to="/feedback">Обратная связь</Link> },
  {
    key: "/analytics",
    icon: <BarChartOutlined />,
    label: <Link to="/analytics">Аналитика</Link>,
    allowedRoles: ["hr", "manager"],
  },
];

const THEME_OPTIONS = [
  { label: "Светлая", value: ThemeMode.Light },
  { label: "Тёмная", value: ThemeMode.Dark },
  { label: "Системная", value: ThemeMode.System },
];

interface AppLayoutProps {
  /** Текущий режим темы. */
  themeMode: ThemeMode;
  /** Сменить режим темы. */
  onThemeChange: (mode: ThemeMode) => void;
  children?: ReactNode;
}

export function AppLayout({
  themeMode,
  onThemeChange,
  children,
}: AppLayoutProps): React.JSX.Element {
  const location = useLocation();
  const { user, signOut } = useAuth();
  const { message } = App.useApp();
  const [collapsed, setCollapsed] = useState(false);
  const navigationToggleRef = useRef<HTMLButtonElement>(null);
  const roleSet = new Set(user?.roles ?? []);
  const navItems = NAV_ITEMS.filter(
    (item) =>
      item.allowedRoles === undefined || item.allowedRoles.some((role) => roleSet.has(role)),
  );
  const menuItems = navItems.map(({ key, icon, label }) => ({ key, icon, label }));

  useEffect(() => {
    const collapseOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !collapsed) {
        setCollapsed(true);
        navigationToggleRef.current?.focus();
      }
    };
    document.addEventListener("keydown", collapseOnEscape);
    return () => document.removeEventListener("keydown", collapseOnEscape);
  }, [collapsed]);

  // Активный пункт — по совпадению начала пути.
  const selectedKey =
    navItems.find((item) => item.key !== "/" && location.pathname.startsWith(item.key))?.key ?? "/";

  const userMenu = {
    items: [
      {
        key: "logout",
        icon: <LogoutOutlined />,
        label: "Выйти",
        onClick: async () => {
          try {
            await signOut();
            message.info("Сессия завершена");
          } catch {
            message.error("Не удалось завершить сессию. Попробуйте ещё раз.");
          }
        },
      },
    ],
  };
  const avatarLetter = (user?.name || user?.email || "У").charAt(0).toUpperCase();

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Header className="vektor-header">
        <Logo />
        <Space>
          <Button
            ref={navigationToggleRef}
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            aria-label={collapsed ? "Развернуть навигацию" : "Свернуть навигацию"}
            aria-expanded={!collapsed}
            aria-controls="primary-navigation"
            onClick={() => setCollapsed((value) => !value)}
          />
          <Segmented
            aria-label="Тема оформления"
            size="small"
            value={themeMode}
            onChange={(value) => onThemeChange(value as ThemeMode)}
            options={THEME_OPTIONS}
          />
          <Dropdown menu={userMenu} placement="bottomRight">
            <Button type="text" aria-label="Открыть меню профиля" style={{ padding: 4 }}>
              <Avatar style={{ backgroundColor: "var(--color-primary)" }}>{avatarLetter}</Avatar>
            </Button>
          </Dropdown>
        </Space>
      </Header>
      <Layout>
        <Sider
          id="primary-navigation"
          breakpoint="md"
          collapsedWidth={0}
          collapsible={false}
          collapsed={collapsed}
          onCollapse={setCollapsed}
          theme="light"
          width={220}
        >
          <Menu mode="inline" selectedKeys={[selectedKey]} items={menuItems} />
        </Sider>
        <Content className="vektor-content">{children ?? <Outlet />}</Content>
      </Layout>
    </Layout>
  );
}
