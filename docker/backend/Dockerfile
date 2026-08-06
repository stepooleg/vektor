# =============================================================================
# Vektor — backend image (Python 3.12 + Django 5 + DRF, Gunicorn).
# Build context — КОРЕНЬ репозитория (см. docker-compose.yml).
# SPEC §11.1: Python 3.12, Gunicorn. On-premise: образ собирается локально.
# =============================================================================
FROM python:3.12-slim AS base

# Системные пакеты для psycopg3 (libpq), Argon2 и сборки.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Сначала ставим зависимости (кеш слоёв), затем — код.
COPY backend/pyproject.toml backend/README.md ./
COPY backend/vektor ./vektor

# Установка зависимостей. Gunicorn включён в runtime-deps (pyproject.toml).
RUN pip install --upgrade pip \
    && pip install -e ".[dev]"

# Копируем остальной код (apps, manage.py и т.д.).
COPY backend/ .

# Non-root пользователь для безопасности (SPEC §12.2).
RUN useradd --create-home --uid 1000 vektor \
    && mkdir -p /app/staticfiles /app/media \
    && chown -R vektor:vektor /app
USER vektor

EXPOSE 8000

# Healthcheck: дёргаем health-эндпоинт (issue #1).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/v1/health/ || exit 1

# Gunicorn — прод-WSGI сервер (SPEC §11.1). 4 воркера для старта.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", \
     "--access-logfile", "-", "--error-logfile", "-", "vektor.wsgi:application"]
