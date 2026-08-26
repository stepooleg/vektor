/**
 * Настройка тестового окружения Vitest + Testing Library (AGENTS.md §3).
 *
 * Подключается через `setupFiles` в `vite.config.ts`.
 */
import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup, configure } from "@testing-library/react";

// Асинхронные lazy-модули и Ant Design могут загружаться дольше секунды
// при параллельном запуске всего набора на CI/Windows.
configure({ asyncUtilTimeout: 5_000 });

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

// jsdom не поддерживает второй (pseudo-element) аргумент getComputedStyle,
// который Ant Design использует только для измерения scrollbar.
const getComputedStyle = window.getComputedStyle.bind(window);
Object.defineProperty(window, "getComputedStyle", {
  writable: true,
  value: (element: Element, pseudoElement?: string | null) =>
    getComputedStyle(element, pseudoElement ? undefined : pseudoElement),
});
