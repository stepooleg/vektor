/**
 * Тесты провайдера темы (BRANDBOOK §8.1, issue #2).
 *
 * Контракт:
 * - тема по умолчанию — системная (учитывает prefers-color-scheme);
 * - ручное переключение выставляет data-theme="light" | "dark" на <html>;
 * - выбор сохраняется (localStorage) и восстанавливается.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";

import { ThemeMode, useTheme } from "./theme";

// Шпионы на window.matchMedia и localStorage.
function mockMatchMedia(prefersDark: boolean): void {
  const listeners: ((e: { matches: boolean }) => void)[] = [];
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: prefersDark && query.includes("dark"),
      media: query,
      onchange: null,
      addEventListener: (_: string, l: (e: { matches: boolean }) => void) => listeners.push(l),
      removeEventListener: (_: string, l: (e: { matches: boolean }) => void) => {
        const i = listeners.indexOf(l);
        if (i >= 0) listeners.splice(i, 1);
      },
      dispatchEvent: () => true,
    })),
  });
}

describe("ThemeProvider / useTheme", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
    mockMatchMedia(false);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("по умолчанию применяет системную тему (light)", () => {
    mockMatchMedia(false);
    const { result } = renderHook(() => useTheme());

    expect(result.current.mode).toBe(ThemeMode.System);
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("применяет системную тему (dark), когда prefers-color-scheme=dark", () => {
    mockMatchMedia(true);
    const { result } = renderHook(() => useTheme());

    expect(result.current.mode).toBe(ThemeMode.System);
    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  it("ручное переключение выставляет data-theme и сохраняет выбор", () => {
    const { result } = renderHook(() => useTheme());

    act(() => {
      result.current.setMode(ThemeMode.Dark);
    });

    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem("vektor-theme")).toBe(ThemeMode.Dark);
  });

  it("восстанавливает сохранённый выбор из localStorage", () => {
    localStorage.setItem("vektor-theme", ThemeMode.Light);
    const { result } = renderHook(() => useTheme());

    expect(result.current.mode).toBe(ThemeMode.Light);
    expect(document.documentElement.dataset.theme).toBe("light");
  });
});
