# Vektor — backend

Django 5 + Django REST Framework, PostgreSQL 16, Celery + Redis.

Стек зафиксирован в [`SPEC.md` §11.1](../SPEC.md) и ADR-0002. Доменная структура —
в [`AGENTS.md` §5](../AGENTS.md).

## Быстрый старт

```bash
cd backend
uv venv --python 3.12 .venv
uv pip install -e ".[dev]"
cp ../.env.example ../.env          # заполнить значения

# Миграции и запуск dev-сервера
uv run python manage.py migrate
uv run python manage.py runserver 8000
```

Health-check: `GET http://localhost:8000/api/v1/health/` → `{"status":"ok",...}`.
Документация API: `http://localhost:8000/api/v1/docs/` (Swagger UI).

## Тесты и качество (AGENTS.md §3, §7.1)

```bash
uv run pytest                                 # Test-First, с покрытием
uv run ruff check . && uv run ruff format --check .
uv run mypy .
```

## Структура настроек

| Модуль                   | Назначение                                   |
|--------------------------|----------------------------------------------|
| `vektor/settings/base.py`| Общие настройки (прод-база, RBAC, DRF)       |
| `vektor/settings/dev.py` | Локальная разработка (DEBUG, SQLite-вывод)   |
| `vektor/settings/test.py`| Автотесты (SQLite in-memory, MD5-хешер)      |

`DJANGO_SETTINGS_MODULE=vektor.settings.dev` (по умолчанию в `manage.py`).

## Секреты

Только через переменные окружения (`.env` в `.gitignore`).
См. [`.env.example`](../.env.example).

## LDAP без привязки к конкретному клиенту

До выбора площадки `AUTH_LDAP_ENABLED=False`: локальная разработка и CI не требуют
корпоративной учётной записи. Полная цепочка `search → user bind → синхронизация`
проверяется автономным Linux contract test с совместимым протоколом `python-ldap`:

```bash
docker compose run --rm backend \
  pytest apps/users/tests/test_ldap_backend.py -q
```

При внедрении администратор заполняет LDAP-параметры из `.env.example`, монтирует
корпоративный CA при необходимости и выполняет smoke test именно LDAP backend:

```bash
docker compose exec backend python manage.py verify_ldap <sAMAccountName-или-UPN>
```

Пароль запрашивается скрыто, не принимается аргументом командной строки и не выводится.
Успешная проверка подтверждает доступность endpoint, CA/TLS, Base DN, service search,
bind пользователя и синхронизацию профиля. Эти значения являются параметрами установки,
а не условием готовности продукта до появления конкретного клиента.

## SMTP без клиентского сервера

Адрес SMTP, учётные данные и доверенный CA являются параметрами установки и не нужны для
локальной разработки или CI. Автономные тесты проверяют разбор конфигурации, запрет
незащищённого удалённого SMTP и отправку через стандартный Django mail backend:

```bash
uv run pytest apps/notifications/tests -q
```

Поддерживаются STARTTLS и implicit SSL. `EMAIL_HOST_USER` и `EMAIL_HOST_PASSWORD` можно
оставить пустыми только вместе — для внутреннего relay, доверяющего IP приложения.
Plaintext SMTP допускается лишь на loopback для локального Mailpit/MailHog.

После заполнения `EMAIL_*` из `.env.example` администратор проверяет реальную доставку на
технический адрес клиента:

```bash
docker compose exec backend python manage.py verify_smtp recipient@example.test
```

Команда не выводит адрес, credentials или содержимое конфигурации. На площадке отдельно
проверяются маршрут, TLS/CA, политика relay и попадание письма в целевой почтовый ящик.

## 1С:ЗУП без клиентского стенда

До выбора площадки `ONEC_SYNC_ENABLED=False`: задача Celery завершается без обращения к
сети и не воспринимает отсутствие настройки как пустую оргструктуру. Продуктовый контракт
проверяется автономно локальным HTTP-сервером без реальных сотрудников:

```bash
uv run pytest apps/orgstructure/tests/test_onec_rest_adapter.py -q
```

Production-адаптер выполняет pull трёх JSON-массивов по HTTPS:
`/orgstructure/departments`, `/orgstructure/positions` и
`/orgstructure/employees?changed_since=…`. Поддерживаются Basic и Bearer/OAuth; секреты,
endpoint и timeout задаются только через `.env`. Записи идентифицируются по `id_1c`, а
`updated_at` защищает более свежие данные от повторного или запоздавшего события.

При внедрении администратор заполняет `ONEC_*` из `.env.example`, проверяет маршрут, TLS/CA,
учётные данные и соответствие JSON-контракта на тестовом наборе клиента, затем включает
`ONEC_SYNC_ENABLED=True`. Первый успешный запуск получает полный снимок, сохраняет cursor,
а следующие передают его как `changed_since`. Полный снимок архивирует исчезнувших
сотрудников; инкрементальная выгрузка применяет явный `is_active=false` и никогда не
трактует отсутствующую запись как увольнение.

## Хранение данных оценок

По умолчанию сырые ответы и комментарии хранятся не более пяти календарных лет. Когда
истекает первый сырой объект цикла, задача сохраняет полный обезличенный агрегат, удаляет
всё сырьё этого цикла и закрывает цикл. Это не зависит от его текущего статуса и не
оставляет частичный либо устаревающий snapshot.
Ежедневная задача `assessment.retention_daily` запускается Celery beat в 03:00 по часовому
поясу приложения. До удаления она либо сохраняет обезличенный read-only агрегат, либо
удаляет агрегат вместе с сырьём — в зависимости от deployment-настройки:

```dotenv
DATA_RETENTION_YEARS=5
ASSESSMENT_AGGREGATE_RETENTION_MODE=archive  # archive или delete
```

Запуск идемпотентен. В audit-log попадают только режим и технические счётчики; оценки,
комментарии и идентификаторы оценщиков туда не записываются. Старое имя
`DATA_RETENTION_MONTHS` временно поддерживается, только если значение кратно 12.
