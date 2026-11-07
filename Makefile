.PHONY: up down logs seed migrate test lint

up:
	./scripts/start.sh

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

seed:
	docker compose exec -T backend python scripts/seed_demo.py

migrate:
	docker compose exec -T backend alembic upgrade head

test:
	pytest -q

lint:
	ruff check app tests alembic scripts
