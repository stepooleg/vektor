#!/usr/bin/env bash
# Vektor — создать суперпользователя Django в контейнере backend.
# Запуск: bash scripts/docker/createsuperuser.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
docker compose run --rm backend python manage.py createsuperuser
