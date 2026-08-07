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
  SolutionOutlined,
  TrophyOutlined,
} from "@ant-design/icons";
import { App, Avatar, Button, Dropdown, Layout, Menu, Segmented, Space } from "antd";
import { useState, type ReactNode } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";

import { Logo } from "@/components/Logo";
import { ThemeMode } from "./theme";
import { useAuth } from "./auth-context";

const { Header, Sider, Content } = Layout;

// Пункты навигации (SPEC §14).
const NAV_ITEMS = [
  { key: "/", icon: <DashboardOutlined />, label: <Link to="/">Дашборд</Link> },
  { key: "/assessment", icon: <CalendarOutlined />, label: <Link to="/assessment">Оценка</Link> },
  {
    key: "/competencies",
    icon: <TrophyOutlined />,
    label: <Link to="/competencies">Компетенции</Link>,
  },
  { key: "/learning", icon: <BookOutlined />, label: <Link to="/learning">Обучение</Link> },
  { key: "/idp", icon: <SolutionOutlined />, label: <Link to="/idp">ИПР</Link> },
  { key: "/portfolio", icon: <FileTextOutlined />, label: <Link to="/portfolio">Портфолио</Link> },
  { key: "/feedback", icon: <HeartOutlined />, label: <Link to="/feedback">Обратная связь</Link> },
  { key: "/analytics", icon: <BarChartOutlined />, label: <Link to="/analytics">Аналитика</Link> },
] as const;

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

  // Активный пункт — по совпадению начала пути.
  const selectedKey =
    NAV_ITEMS.find((item) => item.key !== "/" && location.pathname.startsWith(item.key))?.key ??
    "/";

  const userMenu = {
    items: [
      {
        key: "logout",
        icon: <LogoutOutlined />,
        label: "Выйти",
        onClick: async () => {
          await signOut();
          message.info("Сессия завершена");
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
          <Segmented
            aria-label="Тема оформления"
            size="small"
            value={themeMode}
            onChange={(value) => onThemeChange(value as ThemeMode)}
            options={THEME_OPTIONS}
          />
          <Dropdown menu={userMenu} placement="bottomRight">
            <Button type="text" style={{ padding: 4 }}>
              <Avatar style={{ backgroundColor: "var(--color-primary)" }}>{avatarLetter}</Avatar>
            </Button>
          </Dropdown>
        </Space>
      </Header>
      <Layout>
        <Sider
          collapsible
          collapsed={collapsed}
          onCollapse={setCollapsed}
          theme="light"
          width={220}
        >
          <Menu mode="inline" selectedKeys={[selectedKey]} items={[...NAV_ITEMS]} />
        </Sider>
        <Content className="vektor-content">{children ?? <Outlet />}</Content>
      </Layout>
    </Layout>
  );
}
