#!/usr/bin/env bash
set -euo pipefail

# One-command launcher for the YouTube clone demo.
# Usage:
#   ./scripts/start.sh            # build, migrate, wait for health, seed demo
#   ./scripts/start.sh --no-seed  # build, migrate, wait for health only
#   ./scripts/start.sh --help

cd "$(dirname "$0")/.."

SEED=1
for arg in "$@"; do
  case "$arg" in
    --no-seed) SEED=0 ;;
    --help|-h)
      sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not installed." >&2
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: docker compose v2 is required." >&2
  exit 1
fi

if [ ! -f .env ]; then
  echo "Creating .env from .env.example..."
  cp .env.example .env
fi

echo "Starting containers..."
docker compose up -d --build

echo "Waiting for backend health at http://localhost:8000/health ..."
deadline=$((SECONDS + 240))
until curl -fsS http://localhost:8000/health >/dev/null 2>&1; do
  if [ "$SECONDS" -ge "$deadline" ]; then
    echo "ERROR: backend did not become healthy in time." >&2
    docker compose ps >&2 || true
    docker compose logs --tail=120 backend >&2 || true
    exit 1
  fi
  sleep 2
done

echo "Applying migrations..."
docker compose exec -T backend alembic upgrade head

if [ "$SEED" -eq 1 ]; then
  echo "Seeding demo data..."
  docker compose exec -T backend python scripts/seed_demo.py
fi

echo
echo "Ready: http://localhost:8000"
echo "Swagger: http://localhost:8000/docs"
echo "MinIO console: http://localhost:9001"
echo "Demo users:"
echo "  admin@example.com / Admin12345!"
echo "  moderator@example.com / Moderator12345!"
echo "  user@example.com / User12345!"