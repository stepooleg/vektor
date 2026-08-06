"""Точка входа ASGI (для асинхронных серверов и PWA/websockets в будущем)."""

from __future__ import annotations

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vektor.settings.dev")

application = get_asgi_application()
