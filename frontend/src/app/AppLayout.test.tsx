/** Responsive-тест главного layout (PWA, issue #65). */
import { App as AntdApp } from "antd";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AppLayout } from "./AppLayout";
import { ThemeMode } from "./theme";

vi.mock("./auth-context", () => ({
  useAuth: () => ({
    user: { email: "employee@corp.local", name: "Сотрудник" },
    signOut: vi.fn(),
  }),
}));

describe("AppLayout responsive", () => {
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
});
