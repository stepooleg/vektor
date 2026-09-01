"""Адаптер интеграции с 1С:ЗУП (SPEC §10.1).

Тип интеграции уточняется с ИТ-службой заказчика (SPEC §17 п.1: REST/SOAP/файлы).
Поэтому реализован как абстракция (Protocol) с прототипом REST-адаптера и
фиктивным (in-memory) адаптером для тестов/разработки.

Односторонняя синхронизация: 1С → приложение. Источник правды по оргструктуре — 1С.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Protocol, cast
from urllib.error import URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

if TYPE_CHECKING:
    from collections.abc import Iterator


class OneCIntegrationError(RuntimeError):
    """Безопасная ошибка транспорта или JSON-контракта 1С."""


@dataclass(frozen=True)
class RestOneCConfig:
    """Непротиворечивая конфигурация соединения с REST API 1С."""

    base_url: str
    auth_mode: str
    username: str = ""
    password: str = ""
    oauth_token: str = ""
    timeout_seconds: float = 15.0
    allow_insecure_loopback: bool = False


@dataclass(frozen=True)
class DepartmentDTO:
    """Данные подразделения из 1С (DTO для синхронизации)."""

    code_1c: str
    name: str
    parent_code_1c: str | None = None
    head_code_1c: str | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class PositionDTO:
    """Данные должности из 1С."""

    code_1c: str
    name: str
    updated_at: datetime | None = None


@dataclass(frozen=True)
class EmployeeDTO:
    """Данные сотрудника из 1С (ПДн — комплаенс 152-ФЗ)."""

    code_1c: str  # табельный номер
    email: str
    last_name: str
    first_name: str
    middle_name: str = ""
    department_code_1c: str = ""
    position_code_1c: str = ""
    manager_code_1c: str | None = None
    hire_date: date | None = None
    is_active: bool = True
    updated_at: datetime | None = None


@dataclass(frozen=True)
class OrgStructureSnapshot:
    """Снимок оргструктуры из 1С (все сущности за один запрос)."""

    departments: list[DepartmentDTO]
    positions: list[PositionDTO]
    employees: list[EmployeeDTO]
    is_full: bool = True


class OneCAdapter(Protocol):
    """Интерфейс адаптера 1С:ЗУП (расширяемая абстракция).

    Конкретные реализации: ``RestOneCAdapter`` (REST/OData), ``FileOneCAdapter``
    (обмен через XML/JSON-файлы), ``FakeOneCAdapter`` (тесты/разработка).
    """

    def fetch_snapshot(self, *, changed_since: datetime | None = None) -> OrgStructureSnapshot:
        """Получить полный или инкрементальный снимок оргструктуры из 1С."""
        ...


class FakeOneCAdapter:
    """Фиктивный адаптер для тестов/разработки (без реальной 1С).

    Возвращает снимок из переданных данных; в проде заменяется на реальный
    адаптер через фабрику ``get_onec_adapter()``.
    """

    def __init__(self, snapshot: OrgStructureSnapshot | None = None) -> None:
        """Создать адаптер с заданным снимком (по умолчанию — пустой)."""
        self._snapshot = snapshot or OrgStructureSnapshot(
            departments=[], positions=[], employees=[]
        )

    def fetch_snapshot(self, *, changed_since: datetime | None = None) -> OrgStructureSnapshot:
        """Вернуть предзаготовленный снимок."""
        _ = changed_since
        return self._snapshot


class RestOneCAdapter:
    """Production-адаптер REST/HTTP JSON для 1С:ЗУП."""

    def __init__(self, config: RestOneCConfig) -> None:
        """Настроить endpoint и аутентификацию deployment-среды."""
        parsed_url = urlparse(config.base_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            msg = "ONEC_BASE_URL должен быть абсолютным HTTP(S) URL"
            raise ValueError(msg)
        insecure_loopback = config.allow_insecure_loopback and parsed_url.hostname in {
            "127.0.0.1",
            "localhost",
            "::1",
        }
        if parsed_url.scheme != "https" and not insecure_loopback:
            msg = "ONEC_BASE_URL должен использовать HTTPS"
            raise ValueError(msg)
        if config.auth_mode not in {"basic", "oauth"}:
            msg = "ONEC_AUTH_MODE должен быть basic или oauth"
            raise ValueError(msg)
        self._base_url = config.base_url.rstrip("/")
        if config.timeout_seconds <= 0:
            msg = "ONEC_TIMEOUT_SECONDS должен быть положительным"
            raise ValueError(msg)
        self._timeout_seconds = config.timeout_seconds
        if config.auth_mode == "basic":
            if not config.username or not config.password:
                msg = "ONEC_USERNAME и ONEC_PASSWORD обязательны для Basic auth"
                raise ValueError(msg)
            credentials = base64.b64encode(f"{config.username}:{config.password}".encode()).decode(
                "ascii"
            )
            self._authorization = f"Basic {credentials}"
        else:
            if not config.oauth_token:
                msg = "ONEC_OAUTH_TOKEN обязателен для OAuth"
                raise ValueError(msg)
            self._authorization = f"Bearer {config.oauth_token}"

    def fetch_snapshot(self, *, changed_since: datetime | None = None) -> OrgStructureSnapshot:
        """Получить и преобразовать полный или инкрементальный снимок."""
        employees_path = "/orgstructure/employees"
        if changed_since is not None:
            if changed_since.tzinfo is None:
                msg = "changed_since должен содержать часовой пояс"
                raise ValueError(msg)
            changed_since_utc = changed_since.astimezone(UTC)
            timestamp = changed_since_utc.isoformat().replace("+00:00", "Z")
            employees_path = f"{employees_path}?{urlencode({'changed_since': timestamp})}"
        try:
            departments = [
                _parse_department(item) for item in self._fetch_list("/orgstructure/departments")
            ]
            positions = [
                _parse_position(item) for item in self._fetch_list("/orgstructure/positions")
            ]
            employees = [_parse_employee(item) for item in self._fetch_list(employees_path)]
        except (KeyError, TypeError, ValueError) as error:
            msg = "Некорректные данные 1С: нарушен JSON-контракт"
            raise OneCIntegrationError(msg) from error
        return OrgStructureSnapshot(
            departments=departments,
            positions=positions,
            employees=employees,
            is_full=changed_since is None,
        )

    def _fetch_list(self, path: str) -> list[dict[str, object]]:
        """Выполнить один GET и вернуть JSON-массив объектов."""
        request = Request(
            f"{self._base_url}{path}",
            headers={"Accept": "application/json", "Authorization": self._authorization},
            method="GET",
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                payload: object = json.loads(response.read().decode("utf-8"))
        except (URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as error:
            msg = "Не удалось получить корректный JSON-ответ от 1С"
            raise OneCIntegrationError(msg) from error
        if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
            msg = "Некорректный JSON-контракт 1С: ожидался массив объектов"
            raise OneCIntegrationError(msg)
        return cast(list[dict[str, object]], payload)


def _required_string(item: dict[str, object], key: str) -> str:
    """Прочитать обязательную непустую JSON-строку без неявных преобразований."""
    value = item[key]
    if not isinstance(value, str) or not value.strip():
        msg = f"{key} должен быть непустой строкой"
        raise ValueError(msg)
    return value


def _optional_string(item: dict[str, object], key: str) -> str | None:
    """Прочитать необязательную JSON-строку."""
    value = item.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        msg = f"{key} должен быть строкой или null"
        raise ValueError(msg)
    return value


def _required_datetime(item: dict[str, object], key: str) -> datetime:
    """Прочитать обязательный ISO 8601 timestamp и привести его к UTC."""
    value = _required_string(item, key)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        msg = f"{key} должен содержать часовой пояс"
        raise ValueError(msg)
    return parsed.astimezone(UTC)


def _optional_date(item: dict[str, object], key: str) -> date | None:
    """Прочитать необязательную календарную дату ISO 8601."""
    value = _optional_string(item, key)
    return date.fromisoformat(value) if value is not None else None


def _parse_department(item: dict[str, object]) -> DepartmentDTO:
    """Преобразовать JSON-подразделение в доменный DTO."""
    return DepartmentDTO(
        code_1c=_required_string(item, "id_1c"),
        name=_required_string(item, "name"),
        parent_code_1c=_optional_string(item, "parent_id_1c"),
        head_code_1c=_optional_string(item, "head_id_1c"),
        updated_at=_required_datetime(item, "updated_at"),
    )


def _parse_position(item: dict[str, object]) -> PositionDTO:
    """Преобразовать JSON-должность в доменный DTO."""
    return PositionDTO(
        code_1c=_required_string(item, "id_1c"),
        name=_required_string(item, "name"),
        updated_at=_required_datetime(item, "updated_at"),
    )


def _parse_employee(item: dict[str, object]) -> EmployeeDTO:
    """Преобразовать JSON-сотрудника в доменный DTO."""
    return EmployeeDTO(
        code_1c=_required_string(item, "id_1c"),
        email=_required_string(item, "email"),
        last_name=_required_string(item, "last_name"),
        first_name=_required_string(item, "first_name"),
        middle_name=_optional_string(item, "middle_name") or "",
        department_code_1c=_required_string(item, "department_id_1c"),
        position_code_1c=_required_string(item, "position_id_1c"),
        manager_code_1c=_optional_string(item, "manager_id_1c"),
        hire_date=_optional_date(item, "hire_date"),
        is_active=_optional_boolean(item, "is_active", default=True),
        updated_at=_required_datetime(item, "updated_at"),
    )


def _optional_boolean(item: dict[str, object], key: str, *, default: bool) -> bool:
    """Прочитать JSON boolean без truthy-преобразования строк и чисел."""
    value = item.get(key, default)
    if not isinstance(value, bool):
        msg = f"{key} должен быть boolean"
        raise ValueError(msg)
    return value


def get_onec_adapter() -> OneCAdapter:
    """Выбрать адаптер по deployment-настройкам интеграции."""
    from django.conf import settings

    if not settings.ONEC_SYNC_ENABLED:
        return FakeOneCAdapter()
    return RestOneCAdapter(
        RestOneCConfig(
            base_url=settings.ONEC_BASE_URL,
            auth_mode=settings.ONEC_AUTH_MODE,
            username=settings.ONEC_USERNAME,
            password=settings.ONEC_PASSWORD,
            oauth_token=settings.ONEC_OAUTH_TOKEN,
            timeout_seconds=settings.ONEC_TIMEOUT_SECONDS,
        )
    )


def iter_subordinates_chain(employee_code: str, snapshot: OrgStructureSnapshot) -> Iterator[str]:
    """Вспомогательная функция: цепочка подчинённых кода сотрудника в снимке."""
    current: set[str] = {employee_code}
    while True:
        children = {
            e.code_1c
            for e in snapshot.employees
            if e.manager_code_1c in current and e.code_1c not in current
        }
        if not children:
            return
        current |= children
        yield from children
