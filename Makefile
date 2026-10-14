SHELL := /bin/bash

.PHONY: check check-backend check-frontend db dev api worker web eval test

check: check-backend check-frontend

check-backend:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest -q

check-frontend:
	cd frontend && pnpm lint && pnpm typecheck && pnpm test

db:
	docker compose up -d db

api:
	cd backend && uv run fastapi dev app/main.py

worker:
	cd backend && uv run python -m app.worker

web:
	cd frontend && pnpm dev

eval:
	cd backend && uv run pytest -q -m eval

test:
	cd backend && uv run pytest -q
	cd frontend && pnpm test
