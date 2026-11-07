# Архитектура

Краткая карта слоёв проекта. Правила и ограничения — в `AGENTS.md`.

## Поток запроса

```
HTTP -> routers/ -> services/ -> repositories/ -> PostgreSQL
```

- **routers/** — тонкие эндпоинты FastAPI: валидация через Pydantic-схемы,
  вызов сервисов, формирование ответов. Бизнес-логики здесь нет.
- **services/** — бизнес-логика: права доступа, проверка приватных видео
  (403 до выдачи presigned URL), сценарии загрузки и модерации.
- **repositories/** — только SQLAlchemy-запросы, без бизнес-логики.
  Явные колонки или ORM-модели с `selectinload`, никаких `SELECT *`.
- **schemas/** — Pydantic-схемы, отдельно request/response.
- **models/** — ORM-модели SQLAlchemy 2.0.

## Асинхронность и фон

- Приложение полностью async: FastAPI + SQLAlchemy 2.0 async + asyncpg.
- Тяжёлые операции (превью, транскод) выполняются воркерами ARQ через Redis.
  Роутеры и сервисы только ставят задачи в очередь через enqueue.
- Видео хранится в MinIO (S3 API); отдача — через presigned URL.

## Auth

- JWT: access-токен 15 минут, refresh-токен 7 дней.
- Роли: `user`, `moderator`, `admin`.
- Все эндпоинты, кроме `/health`, требуют auth-зависимость.
- Комментарии и лайки требуют аутентификации; публичные видео доступны без неё.

## Frontend

- Jinja2 + Alpine.js + Tailwind CSS (CDN в скелете).
- Mobile-first, адаптив проверяется на ширине 375px и 1280px.
- Шаблоны в `frontend/templates/`, статика в `frontend/static/`.

## Инфраструктура

- Docker Compose поднимает приложение, PostgreSQL 16, Redis и MinIO.
- Миграции — Alembic; существующие ревизии не изменяются, только новые.
- Секреты — только через `.env` и `pydantic-settings`.