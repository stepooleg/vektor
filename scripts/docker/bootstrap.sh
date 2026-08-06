#!/usr/bin/env bash
# =============================================================================
# Vektor — начальная загрузка dev-окружения в Docker.
# Поднимает БД/Redis, применяет миграции, собирает статику.
# Запуск: bash scripts/docker/bootstrap.sh
# =============================================================================
set -euo pipefail

cd "$(dirname "$0")/../.."

echo "==> Сборка образов…"
docker compose build

echo "==> Запуск БД и Redis (фоном)…"
docker compose up -d db redis

echo "==> Ожидание готовности БД…"
for _ in $(seq 1 30); do
    if docker compose exec -T db pg_isready -U "${POSTGRES_USER:-vektor}" >/dev/null 2>&1; then
        echo "    БД готова."
        break
    fi
    sleep 1
done

echo "==> Применение миграций…"
docker compose run --rm backend python manage.py migrate

echo "==> Сбор статики…"
docker compose run --rm backend python manage.py collectstatic --noinput

echo "==> Готово. Запустите: docker compose up"
