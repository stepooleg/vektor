# Vektor

> Корпоративное HR-приложение: оценка 360°, обучение (LMS), индивидуальные планы
> развития (ИПР), непрерывная обратная связь и портфолио достижений.

**Статус:** активная разработка по фазам (см. [Milestones](https://github.com/stepooleg/vektor/milestones)).

---

## 📖 Документация

| Документ | Описание |
|---|---|
| [SPEC.md](./SPEC.md) | Спецификация продукта (требования заказчика) |
| [BRANDBOOK.md](./BRANDBOOK.md) | Брендбук: цвета, типографика, токены, компоненты |
| [AGENTS.md](./AGENTS.md) | Правила работы в репозитории (для агентов и разработчиков) |

---

## 🧱 Технологический стек

- **Backend:** Python 3.12 · Django 5 · Django REST Framework · PostgreSQL 16 · Celery + Redis
- **Frontend:** React 18 · TypeScript · Vite · Ant Design · Recharts · PWA (Workbox)
- **Инфраструктура:** Docker · Docker Compose · Nginx · Gunicorn
- **Тесты:** pytest (BE) · Vitest + React Testing Library + Playwright (FE)
- **Качество:** ruff · mypy · ESLint · Prettier · TypeScript strict

---

## 🚀 Быстрый старт

```bash
# Клонирование
git clone git@github.com:stepooleg/vektor.git
cd vektor
cp .env.example .env            # заполнить значения

# Полное окружение через Docker (см. docs/deployment/dev-setup.md)
bash scripts/docker/bootstrap.sh
docker compose up
# → frontend:  http://localhost:8080  (или :5173 напрямую в dev)
# → backend:   http://localhost:8000/api/v1/docs/  (Swagger)
# → health:    http://localhost:8000/api/v1/health/
```

### Локальная разработка по слоям

```bash
# Backend (Python 3.12 + uv)
cd backend && uv venv --python 3.12 .venv && uv pip install -e ".[dev]"
uv run python manage.py migrate && uv run python manage.py runserver

# Frontend (Node 20+)
cd frontend && npm ci && npm run dev
```

Команды тестов/качества — в [`AGENTS.md`](./AGENTS.md) §12 и `backend/README.md`,
`frontend/README.md`.

### pre-commit хуки

```bash
pip install pre-commit
pre-commit install           # хук на каждый коммит
pre-commit run --all-files   # прогон на всём репозитории
```

Хуки: ruff (lint+format), mypy (backend), ESLint+Prettier (frontend),
проверки JSON/YAML/TOML, защита секретов. Подробнее: [`.pre-commit-config.yaml`](./.pre-commit-config.yaml).

---

## 📐 Принципы разработки

1. **Качество — приоритет.** Сроки не ограничены (SPEC §16).
2. **Test-First:** сначала тесты, затем реализация (AGENTS.md §3).
3. **Следуем брендбуку:** дизайн-токены, две темы, доступность (BRANDBOOK.md).
4. **Безопасность и анонимность 360°** — критичны (152-ФЗ, SPEC §6.3, §12).
5. **Definition of Done** — в AGENTS.md §10.

---

## 🗺️ Дорожная карта (фазы)

| Фаза | Содержание | Milestone |
|---|---|---|
| **0. Фундамент** | Репозиторий, CI, скелет backend/frontend, Docker | `Фаза 0` |
| **1. MVP: Оценка** | SSO+пароль, 1С:ЗУП, компетенции, 360° + самооценка, анонимность, уведомления | `Фаза 1` |
| **2. Обучение и ИПР** | LMS (тексты/тесты/задания), каталог, ИПР (авто + правка), push (PWA) | `Фаза 2` |
| **3. Аналитика, ОС, портфолио** | Непрерывная ОС, портфолио, расширенная аналитика, экспорт | `Фаза 3` |
| **4. Развитие** | MBO/OKR, сертификаты, мультиязычность, нативное моб. (по приоритетам) | `Фаза 4` |

Актуальный список задач — во [Issues](https://github.com/stepooleg/vektor/issues).

---

## 🔐 Безопасность

Приложение обрабатывает персональные данные сотрудников в соответствии с
**152-ФЗ**. Развёртывание — on-premise в закрытом контуре организации.

- Секреты — только через переменные окружения (`.env` в `.gitignore`).
- Сырые ответы оценщиков 360° недоступны никому, кроме системного audit-log.
- Все действия над чувствительными данными журналируются.

Об обнаруженных уязвимостях сообщать приватно, не создавая публичный issue.

---

## 📜 Лицензия

TBD (определяется заказчиком).
