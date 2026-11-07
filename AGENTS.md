# Правила проекта: YouTube-клон (тестовое задание)

## Стек (не менять без явного указания)

- Backend: Python 3.12, FastAPI, SQLAlchemy 2.0 async, Alembic, PostgreSQL 16
- Хранилище: MinIO (S3 API), presigned URL для отдачи видео
- Очередь: ARQ + Redis (только для тяжёлых операций: превью, транскод)
- Auth: JWT (access 15min, refresh 7d), роли: user / moderator / admin
- Frontend: Jinja2 + Alpine.js + Tailwind CSS (адаптив: mobile-first, breakpoints sm/md/lg)
- Тесты: pytest + pytest-asyncio + httpx.AsyncClient
- Деплой: Docker Compose, одна команда `docker compose up -d --build`

## Жёсткие правила (нарушение = откат коммита)

1. НИКОГДА не коммитить в `main` напрямую. Каждая фича — новая ветка от `main`.
2. Имя ветки: `feat/<краткое-имя>`, `fix/<краткое-имя>`, `chore/<краткое-имя>`.
3. Один коммит = одно логическое изменение. Сообщение коммита: `<type>: <суть>` + тело с «что/зачем/как проверено».
4. Перед коммитом: `pytest` проходит, `ruff check` без ошибок.
5. Не менять существующие миграции Alembic. Только новые ревизии.
6. Не хардкодить секреты. Всё через `.env` + `pydantic-settings`.
7. Все эндпоинты, кроме `/health`, требуют auth-зависимость (явную или через router-level dependency).
8. Приватные видео: проверка доступа ДО выдачи presigned URL. Отказ — 403, не 404 (не раскрывать существование).
9. Комментарии и лайки требуют аутентификации. Просмотр публичных — нет.
10. Адаптивность: любой новый шаблон проверяется на ширине 375px и 1280px.

## Архитектурные границы

- Роутеры — тонкие. Бизнес-логика — в `services/`.
- Репозитории — в `repositories/`, только SQLAlchemy-запросы.
- Схемы Pydantic — в `schemas/`, отдельно request/response.
- Фоновые задачи — в `workers/`, запускаются только через ARQ enqueue.
- Никаких `SELECT *`. Только явные колонки или ORM-модели с `selectinload`.

## Контракт API (не ломать)

- Ошибки: `{"detail": "..."}` (стандарт FastAPI).
- Пагинация: `?page=1&size=20`, ответ `{"items": [], "total": N, "page": 1}`.
- Swagger доступен на `/docs`, OpenAPI JSON на `/openapi.json`.

## Git-гигиена

- Перед началом работы: `git checkout main && git pull && git checkout -b feat/...`
- После завершения: merge в main через `git merge --no-ff` (сохраняет историю ветки).
- Сообщения коммитов — на английском, тело — можно на русском.
