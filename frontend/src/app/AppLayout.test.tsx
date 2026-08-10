/** Responsive-тест главного layout (PWA, issue #65). */
import { App as AntdApp } from "antd";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AppLayout } from "./AppLayout";
import { ThemeMode } from "./theme";

const authState = vi.hoisted(() => ({
  user: {
    email: "employee@corp.local",
    name: "Сотрудник",
    employeeId: 1,
    roles: ["employee"],
  },
}));

vi.mock("./auth-context", () => ({
  useAuth: () => ({
    user: authState.user,
    signOut: vi.fn(),
  }),
}));

describe("AppLayout responsive", () => {
  beforeEach(() => {
    authState.user.roles = ["employee"];
  });

  it("скрывает sidebar ниже breakpoint md", async () => {
    const originalMatchMedia = window.matchMedia;
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: query.includes("max-width"),
        media: query,
        onchange: null,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });
    const { container } = render(
      <AntdApp>
        <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <AppLayout themeMode={ThemeMode.Light} onThemeChange={vi.fn()}>
            <div>Контент</div>
          </AppLayout>
        </MemoryRouter>
      </AntdApp>,
    );

    await waitFor(() => {
      expect(container.querySelector(".ant-layout-sider-zero-width")).toBeInTheDocument();
    });
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: originalMatchMedia,
    });
  });

  it("даёт доступные имена кнопкам профиля и навигации", async () => {
    render(
      <AntdApp>
        <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <AppLayout themeMode={ThemeMode.Light} onThemeChange={vi.fn()}>
            <div>Контент</div>
          </AppLayout>
        </MemoryRouter>
      </AntdApp>,
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Открыть меню профиля" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Свернуть навигацию" })).toBeInTheDocument();
    });
  });

  it("сворачивает навигацию по Escape и возвращает фокус", async () => {
    render(
      <AntdApp>
        <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <AppLayout themeMode={ThemeMode.Light} onThemeChange={vi.fn()}>
            <div>Контент</div>
          </AppLayout>
        </MemoryRouter>
      </AntdApp>,
    );
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Свернуть навигацию" })).toBeInTheDocument();
    });
    fireEvent.keyDown(document, { key: "Escape" });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Развернуть навигацию" })).toHaveFocus();
    });
  });

  it("скрывает административные разделы от сотрудника", async () => {
    authState.user.roles = ["employee"];
    render(
      <AntdApp>
        <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <AppLayout themeMode={ThemeMode.Light} onThemeChange={vi.fn()} />
        </MemoryRouter>
      </AntdApp>,
    );

    await waitFor(() => {
      expect(screen.queryByRole("link", { name: "Аналитика" })).not.toBeInTheDocument();
      expect(screen.queryByRole("link", { name: "Компетенции" })).not.toBeInTheDocument();
    });
  });

  it.each([
    { role: "manager", visible: "Аналитика", hidden: "Компетенции" },
    { role: "methodologist", visible: "Компетенции", hidden: "Аналитика" },
  ])(
    "показывает роли $role только разрешённый административный раздел",
    async ({ role, visible, hidden }) => {
      authState.user.roles = [role];
      render(
        <AntdApp>
          <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
            <AppLayout themeMode={ThemeMode.Light} onThemeChange={vi.fn()} />
          </MemoryRouter>
        </AntdApp>,
      );

      await waitFor(() => {
        expect(screen.getByRole("link", { name: visible })).toBeInTheDocument();
        expect(screen.queryByRole("link", { name: hidden })).not.toBeInTheDocument();
      });
    },
  );

  it("показывает HR все административные разделы", async () => {
    authState.user.roles = ["hr"];
    render(
      <AntdApp>
        <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <AppLayout themeMode={ThemeMode.Light} onThemeChange={vi.fn()} />
        </MemoryRouter>
      </AntdApp>,
    );

    expect(await screen.findByRole("link", { name: "Аналитика" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Компетенции" })).toBeInTheDocument();
  });
});
