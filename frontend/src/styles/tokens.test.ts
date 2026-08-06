/**
 * Тест дизайн-токенов (BRANDBOOK §8.2, issue #2).
 *
 * Контракт: ключевые токены доступны как CSS-переменные на :root
 * и переопределяются в тёмной теме.
 */
import { beforeEach, describe, expect, it } from "vitest";

import "@/styles/tokens.css";

function readVar(name: string, theme?: string): string {
  if (theme) {
    document.documentElement.setAttribute("data-theme", theme);
  } else {
    document.documentElement.removeAttribute("data-theme");
  }
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

describe("Дизайн-токены (tokens.css)", () => {
  beforeEach(() => {
    document.documentElement.removeAttribute("data-theme");
  });

  it("основные токены доступны в светлой теме (:root)", () => {
    // Регистр HEX не регламентируется (CSS-канонизация); сравниваем без учёта.
    expect(readVar("--color-primary").toLowerCase()).toBe("#3b5bdb");
    expect(readVar("--color-accent").toLowerCase()).toBe("#12b886");
    expect(readVar("--bg-base").toLowerCase()).toBe("#f8f9fb");
    expect(readVar("--text-primary").toLowerCase()).toBe("#1a1d23");
  });

  it("токены переопределяются в тёмной теме", () => {
    expect(readVar("--color-primary", "dark").toLowerCase()).toBe("#5c7cfa");
    expect(readVar("--bg-base", "dark").toLowerCase()).toBe("#0f1115");
    expect(readVar("--text-primary", "dark").toLowerCase()).toBe("#f1f3f5");
  });

  it("типографика и радиусы заданы", () => {
    expect(readVar("--font-sans")).toContain("Ubuntu");
    expect(readVar("--radius-md")).toBe("8px");
  });
});
