# ADR 0002. Технологический стек

- **Дата:** 2026-08-06
- **Статус:** Принято
- **Основание:** SPEC.md §11 (Технические рекомендации)

## Контекст

Заказчик делегировал выбор стека исполнителю (SPEC §1.2), но привёл рекомендуемый
набор технологий. Приложение разворачивается on-premise в закрытом контуре, обрабатывает
персональные данные (152-ФЗ), рассчитано на 100–500 пользователей.

## Решение

Принять рекомендуемый стек SPEC §11.1 **без изменений**:

| Слой | Технология |
|---|---|
| Backend | Python 3.12 + Django 5 + Django REST Framework |
| БД | PostgreSQL 16 |
| Очереди/фон | Celery + Redis |
| Frontend | React 18 + TypeScript |
| Сборка/PWA | Vite + Workbox (Service Worker) |
| UI-кит | Ant Design |
| Графики | Recharts |
| Контейнеризация | Docker + Docker Compose |
| Web-сервер | Nginx + Gunicorn |
| SSO/LDAP | django-auth-ldap / python3-saml (уточняется, SPEC §17 п.2) |

Дополнительно (качество и тесты, не из SPEC):

- BE: `pytest`, `pytest-django`, `factory-boy`, `ruff`, `mypy` (strict).
- FE: `Vitest`, `React Testing Library`, `Playwright` (E2E), `ESLint`, `Prettier`, `tsc --strict`.

## Последствия

- Зрелая экосистема Django/DRF удобна для on-premise и интеграций (1С, AD).
- PostgreSQL 16 — JSON-поля для гибких опросников, полнотекстовый поиск.
- TypeScript strict + строгая типизация BE/FE снижают количество ошибок
  (приоритет — качество, AGENTS.md §2).

## Альтернативы

- **FastAPI** — отклонён: монолитная модульная архитектура (ADR 0003) лучше ложится на Django.
- **.NET 8 + ASP.NET Core + Angular** — отклонён: нет .NET-экспертизы в команде.
- **MUI вместо Ant Design** — отложен; Ant Design выбран как дефолт с переопределением
  дизайн-токенов Vektor (BRANDBOOK §6).

## Связанные

- [ADR 0001](./0001-record-architecture-decisions.md)
- [ADR 0003](./0003-modular-monolith.md)
