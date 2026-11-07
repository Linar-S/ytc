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
- тесты создания моделей и каскадного удаления
- заготовки frontend-шаблонов и статики

## [0.1.0] - 2026-11-07

### Added

- chore: скелет проекта (структура app/, Alembic, Docker Compose, frontend, tests)