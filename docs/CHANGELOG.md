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
- фронтенд: сетка карточек на главной, video-тег, лайк и комментарии на `/watch/{id}`
- тесты моделей, auth, загрузки, ленты, лайков и комментариев
- заготовки frontend-шаблонов и статики

## [0.1.0] - 2026-11-07

### Added

- chore: скелет проекта (структура app/, Alembic, Docker Compose, frontend, tests)