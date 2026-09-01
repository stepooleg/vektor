"""Контракт production REST-адаптера 1С:ЗУП (issue #41)."""

from __future__ import annotations

import base64
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import parse_qs, urlsplit

import pytest

from apps.orgstructure.onec_adapter import (
    OneCIntegrationError,
    RestOneCAdapter,
    RestOneCConfig,
)


def _config(base_url: str, **overrides: object) -> RestOneCConfig:
    """Собрать безопасную конфигурацию локального contract test."""
    values: dict[str, object] = {
        "base_url": base_url,
        "auth_mode": "basic",
        "username": "integration-user",
        "password": "integration-password",
        "allow_insecure_loopback": True,
    }
    values.update(overrides)
    return RestOneCConfig(**values)  # type: ignore[arg-type]


@pytest.fixture()
def onec_http_server() -> Iterator[tuple[str, list[tuple[str, str | None]], dict[str, object]]]:
    """Локальный HTTP-контракт без реального стенда или клиентских данных."""
    requests: list[tuple[str, str | None]] = []
    payloads: dict[str, object] = {
        "/orgstructure/departments": [
            {
                "id_1c": "D1",
                "name": "ИТ",
                "parent_id_1c": None,
                "head_id_1c": "E1",
                "updated_at": "2026-08-31T09:00:00Z",
            }
        ],
        "/orgstructure/positions": [
            {
                "id_1c": "P1",
                "name": "Разработчик",
                "updated_at": "2026-08-31T09:01:00Z",
            }
        ],
        "/orgstructure/employees": [
            {
                "id_1c": "E1",
                "email": "employee@example.test",
                "last_name": "Иванов",
                "first_name": "Иван",
                "middle_name": "Иванович",
                "department_id_1c": "D1",
                "position_id_1c": "P1",
                "manager_id_1c": None,
                "hire_date": "2024-01-15",
                "is_active": True,
                "updated_at": "2026-08-31T09:02:00Z",
            }
        ],
    }

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            requests.append((self.path, self.headers.get("Authorization")))
            body = json.dumps(payloads[urlsplit(self.path).path], ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            """Не засорять вывод pytest access-log локального сервера."""
            _ = (format, args)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests, payloads
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_rest_adapter_fetches_full_json_snapshot_with_basic_auth(
    onec_http_server: tuple[str, list[tuple[str, str | None]], dict[str, object]],
) -> None:
    """Адаптер получает три справочника и скрывает HTTP за snapshot seam."""
    base_url, requests, _ = onec_http_server
    adapter = RestOneCAdapter(_config(base_url))

    snapshot = adapter.fetch_snapshot()

    assert snapshot.is_full is True
    assert snapshot.departments[0].code_1c == "D1"
    assert snapshot.departments[0].head_code_1c == "E1"
    assert snapshot.positions[0].code_1c == "P1"
    assert snapshot.employees[0].code_1c == "E1"
    assert snapshot.employees[0].department_code_1c == "D1"
    assert snapshot.employees[0].updated_at == datetime(2026, 8, 31, 9, 2, tzinfo=UTC)
    expected_auth = "Basic " + base64.b64encode(b"integration-user:integration-password").decode(
        "ascii"
    )
    assert requests == [
        ("/orgstructure/departments", expected_auth),
        ("/orgstructure/positions", expected_auth),
        ("/orgstructure/employees", expected_auth),
    ]


def test_rest_adapter_requests_incremental_employees_with_oauth(
    onec_http_server: tuple[str, list[tuple[str, str | None]], dict[str, object]],
) -> None:
    """changed_since передаётся только сотрудникам и помечает снимок частичным."""
    base_url, requests, _ = onec_http_server
    adapter = RestOneCAdapter(
        _config(
            base_url,
            auth_mode="oauth",
            username="",
            password="",
            oauth_token="deployment-token",
        )
    )
    changed_since = datetime(2026, 8, 31, 9, tzinfo=UTC)

    snapshot = adapter.fetch_snapshot(changed_since=changed_since)

    assert snapshot.is_full is False
    assert [urlsplit(path).path for path, _ in requests] == [
        "/orgstructure/departments",
        "/orgstructure/positions",
        "/orgstructure/employees",
    ]
    assert parse_qs(urlsplit(requests[2][0]).query) == {"changed_since": ["2026-08-31T09:00:00Z"]}
    assert all(auth == "Bearer deployment-token" for _, auth in requests)


def test_rest_adapter_rejects_non_list_payload_without_exposing_it(
    onec_http_server: tuple[str, list[tuple[str, str | None]], dict[str, object]],
) -> None:
    """Некорректный контракт завершается безопасной интеграционной ошибкой."""
    base_url, _, payloads = onec_http_server
    payloads["/orgstructure/employees"] = {"employee_secret": "do-not-log"}
    adapter = RestOneCAdapter(_config(base_url))

    with pytest.raises(OneCIntegrationError) as error:
        adapter.fetch_snapshot()

    assert "Некорректный JSON-контракт 1С" in str(error.value)
    assert "do-not-log" not in str(error.value)


def test_rest_adapter_requires_secure_transport_and_credentials() -> None:
    """Production-конфигурация требует HTTPS и непустую пару учётных данных."""
    with pytest.raises(ValueError, match="HTTPS"):
        RestOneCAdapter(
            RestOneCConfig(
                base_url="http://onec.example.test",
                auth_mode="basic",
                username="user",
                password="password",
            )
        )

    with pytest.raises(ValueError, match="ONEC_USERNAME"):
        RestOneCAdapter(RestOneCConfig(base_url="https://onec.example.test", auth_mode="basic"))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id_1c", None),
        ("is_active", "false"),
        ("updated_at", None),
        ("hire_date", "завтра"),
    ],
)
def test_rest_adapter_rejects_invalid_employee_fields(
    onec_http_server: tuple[str, list[tuple[str, str | None]], dict[str, object]],
    field: str,
    value: object,
) -> None:
    """Ключ, boolean и версия источника не приводятся из произвольных JSON-типов."""
    base_url, _, payloads = onec_http_server
    employees = payloads["/orgstructure/employees"]
    assert isinstance(employees, list)
    employee = employees[0]
    assert isinstance(employee, dict)
    employee[field] = value

    with pytest.raises(OneCIntegrationError, match="Некорректные данные 1С"):
        RestOneCAdapter(_config(base_url)).fetch_snapshot()
