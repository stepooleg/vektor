#!/usr/bin/env python
"""Утилита администрирования Django для проекта «Vektor».

Запуск:
    python manage.py <command> [options]
"""

from __future__ import annotations

import os
import sys


def main() -> None:
    """Точка входа для команд ``django-admin``."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vektor.settings.dev")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover - импорт всегда есть в окружении
        msg = (
            "Не удалось импортировать Django. Убедитесь, что виртуальное "
            "окружение активировано и зависимости установлены (uv sync)."
        )
        raise ImportError(msg) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
