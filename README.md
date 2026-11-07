# YouTube Clone

Skeleton FastAPI-приложения YouTube-клона: async SQLAlchemy + PostgreSQL,
Alembic, MinIO (S3), ARQ + Redis, JWT-аутентификация и Jinja2-фронтенд.

## Стек

- Python 3.12, FastAPI, SQLAlchemy 2.0 async, Alembic, PostgreSQL 16
- MinIO (S3 API), ARQ + Redis
- Pytest + pytest-asyncio + httpx, Ruff
- Docker Compose (backend + worker + postgres + redis + minio)

## Быстрый старт

```bash
cp .env.example .env
docker compose up -d --build
curl http://localhost:8000/health
# {"status":"ok"}
```

Проверить миграции и статус сервисов:

```bash
docker compose exec backend alembic upgrade head
docker compose ps
```

Swagger: <http://localhost:8000/docs>, OpenAPI: <http://localhost:8000/openapi.json>.
MinIO Console: <http://localhost:9001> (minioadmin / change-me-minio по умолчанию).

## Аутентификация (демо)

Первый зарегистрированный пользователь получает роль `admin`, последующие — `user`.
Access-токен живёт 15 минут, refresh-токен — 7 дней. При обновлении старый refresh
инвалидируется (ротация с хранением в `refresh_tokens`).

```bash
curl -s -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","username":"alice","password":"correct-horse-battery"}'

curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","password":"correct-horse-battery"}'

# скопируйте access_token из ответа login
curl -s http://localhost:8000/auth/me \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

## Локальная разработка

```bash
python3.12 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
ruff check .
pytest
```

Для локального запуска backend нужны PostgreSQL, Redis и MinIO — проще поднять
инфраструктуру через `docker compose up -d postgres redis minio`, затем запустить
`alembic upgrade head` и `uvicorn app.main:app --reload`.

## Структура

```text
app/
  main.py          # FastAPI app + lifespan (DB pool, MinIO client)
  config.py        # pydantic-settings, .env
  database.py      # async engine/session, Base, get_db
  dependencies.py  # get_current_user, require_role
  routers/         # тонкие HTTP-роутеры
  services/        # бизнес-логика
  repositories/    # SQLAlchemy-запросы
  schemas/         # Pydantic request/response
  models/          # ORM-модели
  workers/         # ARQ WorkerSettings и фоновые задачи
alembic/           # миграции схемы и refresh-токенов
frontend/          # Jinja2-шаблоны и static
tests/             # pytest + httpx
docs/              # CHANGELOG и архитектура
```