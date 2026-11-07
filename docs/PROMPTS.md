# Журнал промптов

Проект: YouTube-клон (тестовое задание).
Инструмент: DeepSeek Harness.
Формат: один раздел на промпт, в хронологическом порядке.

## Как читать этот файл

Каждая запись содержит: дату, ветку, цель промпта, полный текст промпта,
результат (какие файлы созданы/изменены), commit hash.

> Промпты P00–P07 восстановлены из истории текущей сессии Harness.
> `docs/PROMPTS_RAW.md` в репозитории отсутствовал, поэтому полные системные
> сообщения и служебные `current_state`-блоки не дублируются: ниже приведён
> пользовательский текст задачи, который подавался в Harness.

---

## [P00] 2026-11-07 — chore/init-skeleton
**Цель:** инициализация скелета проекта.
**Промпт:**

```text
Контекст: AGENTS.md уже в корне. Репозиторий пуст (только README и .gitignore).

Задача: Создай скелет проекта согласно AGENTS.md.

Шаги:

Создай структуру каталогов: app/ (main.py, config.py, database.py), app/routers/, app/services/, app/repositories/, app/schemas/, app/models/, app/workers/, alembic/, tests/, frontend/ (templates/, static/), docs/.

pyproject.toml с зависимостями: fastapi, uvicorn[standard], sqlalchemy[asyncio], asyncpg, alembic, pydantic-settings, python-jose[cryptography], passlib[bcrypt], minio, arq, redis, jinja2, python-multipart, pytest, pytest-asyncio, httpx, ruff.

docker-compose.yml: postgres:16, redis:7, minio/minio, backend (build: .), worker (тот же образ, command: arq app.workers.settings.WorkerSettings).

Dockerfile: multi-stage, python:3.12-slim, non-root user.

app/main.py: FastAPI app, lifespan (init DB pool, MinIO client), include routers (пока пустые), /health без auth.

.env.example со всеми переменными.

Создай ветку chore/init-skeleton, закоммить, запиши в docs/CHANGELOG.md запись [0.1.0] — chore: скелет проекта.

Критерий готовности: docker compose up -d --build запускается, curl localhost:8000/health → {"status":"ok"}, alembic upgrade head выполняется (пустая миграция).
```

**Результат:** созданы app/, docker-compose.yml, Dockerfile, .env.example, Alembic-скелет, /health, frontend-заготовки, tests/test_health.py.
**Commit:** `3c752f2`

---

## [P01] 2026-11-07 — feat/db-models
**Цель:** SQLAlchemy-модели, миграция initial_schema и базовые Pydantic-схемы.
**Промпт:**

```text
Контекст: Скелет готов. AGENTS.md в силе. Схема БД — в AGENTS.md (раздел «Схема БД»).

Задача: Ветка feat/db-models.

Шаги:

Создай SQLAlchemy-модели в app/models/ для всех таблиц из схемы. Используй Mapped/mapped_column, async-совместимые типы (DateTime(timezone=True), UUID для id).

Создай Alembic-миграцию initial_schema.

Добавь Enum-типы: user_role (user, moderator, admin), video_status (uploading, processing, ready, failed, hidden), visibility (public, private, unlisted).

Индексы: videos(owner_id, created_at), comments(video_id, created_at), subscriptions(subscriber_id), reports(status).

app/schemas/ — базовые Pydantic-схемы для каждой модели (UserCreate, VideoOut, CommentCreate и т.д.).

Напиши tests/test_models.py: создание пользователя, видео, комментария в тестовой БД; проверка каскадного удаления.

Обнови CHANGELOG.

Критерий готовности: alembic upgrade head на чистой БД проходит без ошибок; pytest tests/test_models.py — зелёный.
```

**Результат:** добавлены ORM-модели User, Video, Comment, Like, Subscription, Report; enum-типы; миграция 0002_initial_schema; Pydantic-схемы; tests/test_models.py.
**Commit:** `a1ec05f`

---

## [P02] 2026-11-07 — feat/auth
**Цель:** JWT-аутентификация, регистрация, refresh-ротация и роли.
**Промпт:**

```text
Контекст: Модели готовы. Ветка feat/auth.

Задача: JWT-аутентификация + регистрация + роли.

Шаги:

app/services/auth.py: хеширование (bcrypt), создание/верификация JWT (access 15min, refresh 7d), refresh-ротация (старый refresh инвалидируется).

app/routers/auth.py: POST /auth/register, POST /auth/login, POST /auth/refresh, POST /auth/logout.

Зависимости: get_current_user (из access token), require_role(role) (фабрика зависимостей).

Регистрация: email unique, пароль ≥ 8 символов, роль по умолчанию user. Первый зарегистрированный пользователь — admin (для демо).

Тесты: регистрация (успех/дубликат/слабый пароль), логин (успех/неверный пароль), доступ к защищённому эндпоинту без токена → 401, с токеном → 200, require_role("admin") для user → 403.

Ветка feat/auth, коммит, CHANGELOG.

Критерий готовности: сценарий curl: register → login → GET /auth/me с токеном → 200.
```

**Результат:** добавлены сервис auth, роутер /auth, get_current_user/require_role, RefreshToken и миграция 0003_refresh_tokens, tests/test_auth.py.
**Commit:** `c82c6af`

---

## [P03] 2026-11-07 — feat/video-upload
**Цель:** прямая загрузка видео в MinIO через presigned URL.
**Промпт:**

```text
Контекст: Auth готов. Ветка feat/video-upload.

Задача: Загрузка видео в MinIO с прогрессом и созданием записи в БД.

Архитектурное решение (следуй ему): Клиент запрашивает presigned URL у backend, грузит файл напрямую в MinIO, затем сообщает backend о завершении. Backend не проксирует байты видео. Это стандартная практика для S3/MinIO .

Шаги:

app/services/storage.py: обёртка MinIO-клиента (ensure_bucket, presigned_put_url, presigned_get_url, stat_object).

app/routers/videos.py:

POST /videos/init-upload: создаёт запись videos со статусом uploading, возвращает video_id, upload_url (presigned PUT, TTL 1 час), object_key.

POST /videos/{id}/complete-upload: проверяет, что объект существует в MinIO, ставит статус processing, enqueue ARQ-задачу на генерацию превью (заглушка в worker).

Валидация: MIME video/*, лимит 2GB (проверка в init-upload по заголовку Content-Length).

app/workers/tasks.py: process_video(video_id) — заглушка: await asyncio.sleep(2), ставит статус ready, генерирует placeholder-превью (или извлекает кадр через ffmpeg, если доступен).

Фронт: страница /upload с <input type="file">, XHR с upload.onprogress, после успеха — redirect на /watch/{id}.

Тесты: init-upload без auth → 401; init-upload с неверным MIME → 400; complete-upload для несуществующего объекта → 404; полный цикл (mock MinIO) → статус ready.

CHANGELOG.

Критерий готовности: загрузка файла через фронт, прогресс-бар доходит до 100%, видео появляется в БД со статусом ready, presigned GET URL открывает видео.
```

**Результат:** добавлены storage-сервис, /videos/init-upload и complete-upload, ARQ process_video, /upload и /watch, MINIO_PUBLIC_ENDPOINT, tests/test_video_upload.py.
**Commit:** `d96bd39`

---

## [P04] 2026-11-07 — feat/watch-and-social
**Цель:** лента, страница просмотра, лайки и комментарии.
**Промпт:**

```text
Контекст: Загрузка работает. Ветка feat/watch-and-social.

Задача: Главная лента, страница просмотра, лайки, комментарии.

Шаги:

GET /videos — лента: только visibility=public, status=ready, сортировка created_at DESC, пагинация.

GET /videos/{id} — метаданные + presigned GET URL (TTL 6 часов). Если visibility=private: проверить video_access или owner_id == current_user.id, иначе 403.

POST /videos/{id}/like / DELETE /videos/{id}/like — идемпотентно (ON CONFLICT DO NOTHING / DELETE). Счётчик лайков — агрегация при чтении или денормализованное поле с периодическим пересчётом.

GET /videos/{id}/comments — пагинация, сортировка created_at DESC.

POST /videos/{id}/comments — auth required, текст 1–2000 символов.

Фронт: главная (сетка карточек с превью), /watch/{id} (video-тег, лайк, форма комментария, список).

Адаптивность: сетка 1 колонка на mobile, 3–4 на desktop.

Тесты: лента не показывает private; лайк дважды → счётчик 1; комментарий без auth → 401; пагинация корректна.

CHANGELOG.

Критерий готовности: полный сценарий ТЗ: регистрация → загрузка → просмотр → лайк → комментарий.
```

**Результат:** добавлены feed/detail/like/comments API, сервис social, репозитории likes/comments, главная сетка и watch UI, tests/test_watch_and_social.py.
**Commit:** `3561df9`

---

## [P05] 2026-11-07 — feat/channels
**Цель:** страница канала, подписки и управляемый доступ к private-видео.
**Промпт:**

```text
Контекст: Социальные функции работают. Ветка feat/channels.

Задача: Страница канала, подписка, приватные видео.

Шаги:

GET /channels/{user_id} — публичная информация: имя, количество видео, подписчиков. Видео канала — только public (или private, если смотритель — владелец/разрешённый).

POST /channels/{user_id}/subscribe / DELETE — идемпотентно.

Управление доступом к приватным видео: POST /videos/{id}/access (только owner) — добавить user_id в video_access; DELETE — убрать.

Фронт: /channel/{id} — шапка с кнопкой подписки, сетка видео. Владелец видит свои private видео с бейджем.

Тесты: подписка идемпотентна; доступ к private видео разрешённому → 200, постороннему → 403; owner видит свои private в канале.

CHANGELOG.

Критерий готовности: пользователь A загружает private видео, разрешает пользователю B, B видит его в канале A и может смотреть; C получает 403.
```

**Результат:** добавлены channels/subscriptions API, модель VideoAccess и миграция 0004_video_access, owner-only grants, /channel/{id} с бейджами private, tests/test_channels.py.
**Commit:** `f91b3a7`

---

## [P06] 2026-11-07 — feat/search-moderation
**Цель:** поиск, жалобы, очередь модерации и hide/unhide.
**Промпт:**

```text
Контекст: Каналы готовы. Ветка feat/search-moderation.

Задача: Поиск по названию + жалобы + скрытие видео модератором.

Шаги:

GET /search?q=... — ILIKE '%q%' по videos.title + description (только ready+public). Индекс GIN/trgm опционально.

POST /videos/{id}/report — auth required, reason из enum (spam, illegal, harassment, other), rate limit: 5 жалоб/час на пользователя (простая проверка по count с created_at > now() - 1 hour).

GET /moderation/queue — только moderator/admin: список видео с жалобами, сортировка по количеству жалоб.

POST /moderation/videos/{id}/hide — moderator/admin: status=hidden, запись в moderation_actions.

POST /moderation/videos/{id}/unhide — восстановление.

Автоскрытие: при ≥ 5 жалобах от разных пользователей — автоматически status=hidden (в сервисе жалоб).

Фронт: страница /moderation (только для moderator/admin), кнопки Hide/Unhide. Кнопка «Пожаловаться» на странице просмотра.

Тесты: user не видит очередь модерации (403); moderator скрывает видео → видео исчезает из ленты; auto-hide при 5 жалобах; rate limit срабатывает.

CHANGELOG.

Критерий готовности: модератор скрывает видео, оно пропадает из публичной ленты и поиска, но остаётся доступным по прямой ссылке для модератора.
```

**Результат:** добавлены /search, /videos/{id}/report с rate limit и auto-hide, moderation queue/hide/unhide, ModerationAction и миграция 0005_moderation_actions, /moderation и report UI, tests/test_search_moderation.py.
**Commit:** `09f1f43`

---

## [P07] 2026-11-07 — chore/polish-deploy
**Цель:** развёртывание одной командой, seed демо-данных и документация.
**Промпт:**

```text
Контекст: Все фичи готовы. Ветка chore/polish-deploy.

Задача: Довести до состояния «разворачивается одной командой».

Шаги:

Проверить все шаблоны на 375px и 1280px. Исправить переполнения, скрыть второстепенные элементы на mobile.

docker-compose.yml: healthchecks для postgres/redis/minio, depends_on: condition: service_healthy, backend ждёт БД, worker ждёт redis.

Скрипт scripts/seed_demo.py: создаёт 3 пользователей (admin, moderator, user), 5 видео (с реальными presigned URL на тестовые файлы в MinIO), комментарии, лайки. Запускается через docker compose exec backend python scripts/seed_demo.py.

README.md: одна команда docker compose up -d --build && docker compose exec backend alembic upgrade head && docker compose exec backend python scripts/seed_demo.py. Учётные данные демо-пользователей.

docs/ARCHITECTURE.md: схема компонентов, поток загрузки (sequence), решения по безопасности.

Прогнать полный сценарий на чистой ВМ (или docker compose down -v && docker compose up).

CHANGELOG, merge в main.

Критерий готовности: на чистой Ubuntu: клонировать, docker compose up -d --build, дождаться healthy, выполнить seed, открыть localhost:8000 — лента с демо-видео, вход под демо-пользователем, загрузка нового файла, лайк, комментарий.
```

**Результат:** добавлены scripts/seed_demo.py, one-command README, обновлён ARCHITECTURE с sequence/security, адаптивная полировка шаблонов, Dockerfile копирует scripts.
**Commit:** `ad89bfd`

---

## Сводка

| ID | Дата | Ветка | Цель | Commit |
|----|------|-------|------|--------|
| P00 | 2026-11-07 | chore/init-skeleton | инициализация скелета проекта. | `3c752f2` |
| P01 | 2026-11-07 | feat/db-models | SQLAlchemy-модели, миграция initial_schema и базовые Pydantic-схемы. | `a1ec05f` |
| P02 | 2026-11-07 | feat/auth | JWT-аутентификация, регистрация, refresh-ротация и роли. | `c82c6af` |
| P03 | 2026-11-07 | feat/video-upload | прямая загрузка видео в MinIO через presigned URL. | `d96bd39` |
| P04 | 2026-11-07 | feat/watch-and-social | лента, страница просмотра, лайки и комментарии. | `3561df9` |
| P05 | 2026-11-07 | feat/channels | страница канала, подписки и управляемый доступ к private-видео. | `f91b3a7` |
| P06 | 2026-11-07 | feat/search-moderation | поиск, жалобы, очередь модерации и hide/unhide. | `09f1f43` |
| P07 | 2026-11-07 | chore/polish-deploy | развёртывание одной командой, seed демо-данных и документация. | `ad89bfd` |

## Замечания

- Промпты P00–P07 следовали шаблону: system prompt (неизменный) + AGENTS.md + current_state + task.
- Кэширование DeepSeek: префикс (system + AGENTS.md) не менялся между запросами.
- Полные логи сессий — в архиве экспорта Harness; в репозитории `docs/PROMPTS_RAW.md` отсутствовал.
- Промпты не перефразированы: перенесён сохранённый пользовательский текст задач.
