"""Проверки согласованности dev-маршрутизации Docker Compose."""

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_dev_frontend_listens_on_nginx_upstream_port() -> None:
    """Vite в dev должен слушать тот же container-port, что и Nginx."""
    if not (PROJECT_ROOT / "docker-compose.override.yml").exists():
        pytest.skip("Корень репозитория не смонтирован в backend-контейнер")

    override = (PROJECT_ROOT / "docker-compose.override.yml").read_text(encoding="utf-8")
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    nginx = (PROJECT_ROOT / "docker" / "nginx" / "nginx.conf").read_text(encoding="utf-8")

    assert 'command: ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "80"]' in override
    assert '"${FRONTEND_PORT_HOST:-5173}:80"' in override
    assert "proxy_pass http://frontend:80;" in nginx
    assert "wget -qO- http://127.0.0.1/" in compose
