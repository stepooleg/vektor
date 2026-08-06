# Локальная разработка через Docker

Окружение `docker compose up` поднимает все сервисы Vektor в on-premise-совместимой
конфигурации (SPEC §11.1, §11.2):

| Сервис    | Образ              | Назначение                                  | Порт (host) |
|-----------|--------------------|---------------------------------------------|-------------|
| `db`      | `postgres:16-alpine` | PostgreSQL 16                             | `5432` (dev)|
| `redis`   | `redis:7-alpine`     | брокер Celery + кеш                        | `6379` (dev)|
| `backend` | `vektor-backend`     | Django + DRF (Gunicorn / runserver в dev)  | `8000` (dev)|
| `frontend`| `vektor-frontend`    | React SPA (Nginx serve / Vite dev)         | `5173` (dev)|
| `nginx`   | `nginx:1.27-alpine`  | reverse-proxy, раздача, TLS-терминация     | `8080`      |

## Предварительные требования

- Docker + Docker Compose v2
- Скопировать `.env.example` → `.env` и заполнить секреты (БД, SECRET_KEY, SMTP и т.д.)

## Быстрый старт

```bash
cp .env.example .env          # заполнить значения

# Первичная инициализация: сборка + миграции + collectstatic
bash scripts/docker/bootstrap.sh

# Запуск всех сервисов
docker compose up
```

После старта:

- Frontend (через Nginx): http://localhost:8080
- Backend API / Swagger: http://localhost:8000/api/v1/docs/ (в dev напрямую)
- Health-check: http://localhost:8000/api/v1/health/

## Типовые операции

```bash
# Миграции
bash scripts/docker/migrate.sh

# Суперпользователь
bash scripts/docker/createsuperuser.sh

# Пересобрать образы после изменения зависимостей
docker compose build

# Логи конкретного сервиса
docker compose logs -f backend

# Остановить
docker compose down            # с удалением контейнеров
docker compose down -v         # также удалить volume БД/Redis (ОСТОРОЖНО: потеря данных)
```

## Dev-режим (`docker-compose.override.yml`)

Применяется автоматически при `docker compose up` и перекрывает прод-настройки:

- `backend` запускается через `runserver` с авто-reload; код монтируется томом.
- `frontend` запускает Vite dev server с HMR; код монтируется томом.
- Порты БД/Redis/backend/frontend доступны напрямую с хоста.

Чтобы запустить «чистую» прод-конфигурацию (без dev-override):

```bash
docker compose -f docker-compose.yml up --build
```

## Замечания

- Образы используют **pinned-версии** (SPEC §11.1): `postgres:16-alpine`,
  `redis:7-alpine`, `python:3.12-slim`, `node:20-alpine`, `nginx:1.27-alpine`.
- Секретов в compose-файлах нет — только ссылки на переменные из `.env`.
- TLS-терминация в проде выполняется на краю периметра (SPEC §12.2);
  базовый nginx здесь — для reverse-proxy и раздачи статики.
