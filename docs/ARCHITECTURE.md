# Архитектура

Карта компонентов, основных потоков и решений по безопасности.
Правила разработки — в `AGENTS.md`.

## Компоненты

```text
Browser (Jinja2 + Alpine.js + Tailwind, XHR)
   │
   ▼
FastAPI backend (uvicorn)
   ├── routers/        HTTP, auth-зависимости, Pydantic-валидация
   ├── services/       бизнес-логика, права доступа, presigned URL
   ├── repositories/   SQLAlchemy-запросы
   ├── models/         ORM (SQLAlchemy 2.0 async)
   ├── workers/        ARQ-задачи (превью, обработка)
   │
   ├── PostgreSQL 16   users, videos, comments, likes, subscriptions,
   │                   reports, video_access, moderation_actions, refresh_tokens
   ├── Redis 7         ARQ queue
   └── MinIO           видео и превью (S3 API)

Docker Compose: postgres + redis + minio + backend + worker
```

- **Роутеры тонкие**: валидируют вход, вызывают сервис, возвращают схему.
- **Сервисы** содержат бизнес-правила и проверки доступа.
- **Репозитории** — только SQLAlchemy-запросы, без бизнес-логики.
- **Фоновые задачи** запускаются только через ARQ enqueue.

## Поток загрузки видео (sequence)

```text
Client            Backend                 MinIO              ARQ/Redis
  │                  │                      │                    │
  │ POST /videos/    │                      │                    │
  │ init-upload      │                      │                    │
  ├─────────────────►│ проверка MIME/2GB    │                    │
  │                  │ INSERT videos         │                    │
  │                  │   status=uploading    │                    │
  │                  │ presigned PUT (1h) ──►│                    │
  │◄─────────────────┤ video_id, upload_url  │                    │
  │                  │                      │                    │
  │ PUT file (XHR progress) ───────────────►│                    │
  │                  │                      │                    │
  │ POST /videos/    │                      │                    │
  │ {id}/complete    │                      │                    │
  ├─────────────────►│ stat_object ────────►│                    │
  │                  │◄─────────────────────┤                    │
  │                  │ status=processing     │                    │
  │                  │ enqueue process_video ───────────────────►│
  │◄─────────────────┤ 200                  │                    │
  │                  │                      │   worker: preview  │
  │                  │                      │◄───────────────────┤
  │                  │ UPDATE status=ready  │                    │
  │                  │ thumbnail_key        │                    │
  │                  │                      │                    │
  │ GET /watch/{id}  │ presigned GET (6h) ─►│                    │
  │◄─────────────────┤ playback_url         │                    │
  │ GET video ─────────────────────────────►│                    │
```

TTL: upload URL — 1 час, playback URL — 6 часов. Backend не проксирует байты видео.

## Просмотр, лента и social

- `GET /videos` — только `public` + `ready`, newest first, пагинация.
- `GET /videos/{id}` — метаданные + presigned GET URL.
- `POST/DELETE /videos/{id}/like` — идемпотентно, счётчик агрегируется при чтении.
- `GET/POST /videos/{id}/comments` — пагинация и auth для создания.
- `GET /channels/{id}` — публичный профиль и видимые видео.
- `POST/DELETE /channels/{id}/subscribe` — идемпотентная подписка.
- `POST/DELETE /videos/{id}/access` — owner-only гранты для private-видео.
- `GET /search?q=` — ILIKE по title/description, только public+ready.
- `GET /moderation/queue`, hide/unhide — только moderator/admin.

## Решения по безопасности

- **JWT**: access 15 минут, refresh 7 дней; refresh-ротация с хранением `jti`
  в `refresh_tokens`, старый refresh отзывается.
- **Пароли**: bcrypt через passlib; в БД только хеш.
- **Роли**: `user` / `moderator` / `admin`; RBAC через `require_role`.
- **Приватные видео**: проверка доступа выполняется ДО выдачи presigned URL.
  Отказ — 403, не 404, чтобы не раскрывать существование объекта.
- **video_access**: owner может выдать доступ конкретному пользователю.
- **Скрытые видео**: `status=hidden` убирает видео из ленты/поиска; прямой доступ
  оставлен owner и moderator/admin.
- **Жалобы**: enum-причины, rate limit 5/час, автоскрытие при 5 разных авторах.
- **Секреты**: только `.env` + `pydantic-settings`; `.env` не попадает в image.
- **MinIO**: клиент для внутренних операций и отдельный публичный endpoint для
  подписи URL, который должен резолвиться из браузера.
- **Docker**: backend/worker работают non-root; healthchecks + `depends_on:
  service_healthy` гарантируют порядок запуска.

## Инфраструктура и деплой

- `docker compose up -d --build` поднимает postgres, redis, minio, backend, worker.
- Backend автоматически применяет `alembic upgrade head` перед uvicorn.
- `python scripts/seed_demo.py` создаёт демо-данные и загружает тестовые объекты
  в MinIO (идемпотентно).
- Миграции только новые; существующие ревизии не изменяются.