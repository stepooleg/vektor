/**
 * Настройка тестового окружения Vitest + Testing Library (AGENTS.md §3).
 *
 * Подключается через `setupFiles` в `vite.config.ts`.
 */
import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

// Очистка DOM между тестами (изоляция RTL).
afterEach(() => {
  cleanup();
});

/**
 * jsdom не реализует window.matchMedia; мокаем минимально жизнеспособной
 * версией, достаточной для провайдера темы (BRANDBOOK §8.1).
 */
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});
