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
  routers/         # тонкие HTTP-роутеры
  services/        # бизнес-логика
  repositories/    # SQLAlchemy-запросы
  schemas/         # Pydantic request/response
  models/          # ORM-модели
  workers/         # ARQ WorkerSettings и фоновые задачи
alembic/           # миграции (0001_initial — пустая)
frontend/          # Jinja2-шаблоны и static
tests/             # pytest + httpx
docs/              # CHANGELOG и архитектура
```