# Changelog

Все заметные изменения проекта документируются в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
версии следуют [Semantic Versioning](https://semver.org/lang/ru/).

## [Unreleased]

### Added

- SQLAlchemy-модели `User`, `Video`, `Comment`, `Like`, `Subscription`, `Report`
- Enum-типы `user_role`, `video_status`, `visibility`
- индексы для видео, комментариев, подписок и модерационных отчётов
- Alembic-миграция `0002_initial_schema`
- Pydantic request/response-схемы для всех моделей
- JWT-аутентификация: регистрация, login, refresh-ротация, logout, `/auth/me`
- зависимости `get_current_user` и `require_role` с проверкой ролей
- bcrypt-хеширование паролей и refresh-token storage с отзывом старых токенов
- Alembic-миграция `0003_refresh_tokens`
- direct-to-MinIO загрузка видео через presigned PUT URL
- endpoints `/videos/init-upload` и `/videos/{id}/complete-upload`
- ARQ-задача `process_video` с placeholder-превью и статусом `ready`
- публичная лента `GET /videos` с пагинацией и presigned thumbnail URL
- `GET /videos/{id}` с presigned playback URL TTL 6 часов и проверкой доступа
- идемпотентные `POST/DELETE /videos/{id}/like` с агрегированным счётчиком
- `GET/POST /videos/{id}/comments` с пагинацией и auth для создания
- страницы каналов `/channels/{id}` и `/channel/{id}` с подпиской и сеткой видео
- идемпотентные `POST/DELETE /channels/{id}/subscribe`
- выдача доступа к private-видео: `POST/DELETE /videos/{id}/access`
- модель и Alembic-миграция `0004_video_access`
- фронтенд: сетка карточек, video-тег, лайк и комментарии на `/watch/{id}`
- поиск `GET /search` по title/description только для public+ready
- жалобы на видео с enum-причинами и rate limit 5/час
- автоскрытие видео при 5 жалобах от разных пользователей
- moderation queue и hide/unhide для moderator/admin
- модель и Alembic-миграция `0005_moderation_actions`
- фронтенд `/moderation` и кнопка «Пожаловаться» на `/watch`
- тесты моделей, auth, загрузки, ленты, лайков, комментариев, каналов и модерации
- seed-скрипт демо-данных и загрузка тестовых объектов в MinIO
- deploy polish: healthchecks/depends_on, README одной командой, architecture sequence
- адаптивная полировка шаблонов: mobile-first, скрытие второстепенных nav-элементов
- заготовки frontend-шаблонов и статики

## [0.2.0] - 2026-11-07

### Added

- docs: журнал промптов (`docs/PROMPTS.md`)

## [0.1.0] - 2026-11-07

### Added

- chore: скелет проекта (структура app/, Alembic, Docker Compose, frontend, tests)