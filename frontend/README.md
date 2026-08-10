# Vektor — frontend

React 18 + TypeScript (strict) + Vite + Ant Design + Recharts. PWA (Workbox) — позже.

Стек зафиксирован в [`SPEC.md` §11.1](../SPEC.md) и ADR-0002. Дизайн-токены —
из [`BRANDBOOK.md` §8.2](../BRANDBOOK.md) (см. `src/styles/tokens.css`).
**Хардкод-HEX запрещён** — только дизайн-токены (BRANDBOOK §10.2).

## Быстрый старт

```bash
cd frontend
npm ci
npm run dev            # http://localhost:5173 (проксирует /api → :8000)
```

## Скрипты

| Команда                | Назначение                           |
| ---------------------- | ------------------------------------ |
| `npm run dev`          | dev-сервер Vite (HMR)                |
| `npm run build`        | прод-сборка (`tsc -b && vite build`) |
| `npm run preview`      | локальный предпросмотр сборки        |
| `npm test`             | Vitest (однократный прогон)          |
| `npm run test:watch`   | Vitest в режиме watch                |
| `npm run test:e2e`     | Playwright E2E в Chromium            |
| `npm run lint`         | ESLint                               |
| `npm run typecheck`    | `tsc --noEmit` (strict)              |
| `npm run format`       | Prettier (запись)                    |
| `npm run format:check` | Prettier (проверка)                  |

## Структура (AGENTS.md §5)

```
src/
├── app/        # shell, провайдеры тем, роутинг, layout
├── pages/      # экраны (по SPEC §14)
├── components/ # переиспользуемые UI-компоненты
├── api/        # клиент к DRF (позже)
├── features/   # составные пользовательские сценарии доменов
├── styles/     # дизайн-токены (tokens.css), глобальные стили
├── test/       # настройка Vitest + Testing Library
└── utils/
```

Перед первым локальным E2E-прогоном установите браузер: `npx playwright install chromium`.
Playwright запускает Vite на `http://127.0.0.1:4173`; тестовые API-ответы изолированно
мокаются в browser-сценариях.

## Темизация

Тема — системная по умолчанию (`prefers-color-scheme`), переключается вручную
(светлая / тёмная / системная) в шапке. Все цвета — через CSS-переменные
(`data-theme` на `<html>`); AntD-компоненты получают токены через
`ConfigProvider` (`src/app/antdTheme.ts`).

## Известные ограничения (Phase 0)

- `react-router-dom@6.30.4` остаётся в диапазоне moderate-advisory
  (open redirect via backslash). Фикс требует React Router 7, что нарушает
  зафиксированный стек (SPEC §11.1 — React 18 / Router 6). На старте навигация
  не использует user-supplied URL, риск минимален; обновим при переходе на
  React 19 / Router 7 (по согласованию). См. ADR-0002.
