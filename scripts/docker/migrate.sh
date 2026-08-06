#!/usr/bin/env bash
# Vektor — применить миграции Django в контейнере backend.
# Запуск: bash scripts/docker/migrate.sh [доп. аргументы manage.py migrate]
set -euo pipefail
cd "$(dirname "$0")/../.."
docker compose run --rm backend python manage.py migrate "$@"
