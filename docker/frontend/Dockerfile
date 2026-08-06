# =============================================================================
# Vektor — frontend image.
# Multi-stage: build (Node 20 + Vite) → serve статики через Nginx.
# Build context — КОРЕНЬ репозитория (см. docker-compose.yml), чтобы иметь
# доступ и к frontend/, и к docker/frontend/nginx-spa.conf.
# SPEC §11.1: React + Vite + PWA. On-premise: статика отдаётся Nginx.
# =============================================================================

# --- Stage 1: сборка production-бандла ---
FROM node:20-alpine AS builder
WORKDIR /app

# Кеш зависимостей: сначала lock-файл.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ .
RUN npm run build

# --- Stage 2: Nginx раздаёт собранную статику ---
FROM nginx:1.27-alpine AS serve

# Удаляем дефолтный vhost, кладём SPA-конфиг (отдаёт статику + SPA-fallback).
# nginx-spa.conf копируется через корневой build-context (см. docker-compose.yml).
RUN rm /etc/nginx/conf.d/default.conf
COPY docker/frontend/nginx-spa.conf /etc/nginx/conf.d/vektor.conf

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

# Healthcheck: Nginx отвечает 200 на корень (127.0.0.1 — IPv4, надёжно в Alpine).
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://127.0.0.1/ >/dev/null 2>&1 || exit 1

CMD ["nginx", "-g", "daemon off;"]
