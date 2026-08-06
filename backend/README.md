# Vektor — backend

Django 5 + Django REST Framework, PostgreSQL 16, Celery + Redis.

Стек зафиксирован в [`SPEC.md` §11.1](../SPEC.md) и ADR-0002. Доменная структура —
в [`AGENTS.md` §5](../AGENTS.md).

## Быстрый старт

```bash
cd backend
uv venv --python 3.12 .venv
uv pip install -e ".[dev]"
cp ../.env.example ../.env          # заполнить значения

# Миграции и запуск dev-сервера
uv run python manage.py migrate
uv run python manage.py runserver 8000
```

Health-check: `GET http://localhost:8000/api/v1/health/` → `{"status":"ok",...}`.
Документация API: `http://localhost:8000/api/v1/docs/` (Swagger UI).

## Тесты и качество (AGENTS.md §3, §7.1)

```bash
uv run pytest                                 # Test-First, с покрытием
uv run ruff check . && uv run ruff format --check .
uv run mypy .
```

## Структура настроек

| Модуль                   | Назначение                                   |
|--------------------------|----------------------------------------------|
| `vektor/settings/base.py`| Общие настройки (прод-база, RBAC, DRF)       |
| `vektor/settings/dev.py` | Локальная разработка (DEBUG, SQLite-вывод)   |
| `vektor/settings/test.py`| Автотесты (SQLite in-memory, MD5-хешер)      |

`DJANGO_SETTINGS_MODULE=vektor.settings.dev` (по умолчанию в `manage.py`).

## Секреты

Только через переменные окружения (`.env` в `.gitignore`).
См. [`.env.example`](../.env.example).
