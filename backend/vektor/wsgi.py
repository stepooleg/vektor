"""Точка входа WSGI для прод-сервера (Gunicorn)."""

from __future__ import annotations

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vektor.settings.dev")

application = get_wsgi_application()
