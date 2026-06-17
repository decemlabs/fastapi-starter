.PHONY: install run test lint fmt typecheck check migrate revision up down

install:        ## Install all dependencies (incl. dev)
	uv sync --extra dev

run:            ## Run the dev server with autoreload
	uv run uvicorn app.main:app --reload

test:           ## Run the test suite
	uv run pytest

lint:           ## Lint with ruff
	uv run ruff check .

fmt:            ## Format with ruff
	uv run ruff format .

typecheck:      ## Static type checking (mypy strict + pyright strict)
	uv run mypy
	uv run pyright

check:          ## Run every gate: lint, types, tests
	uv run ruff check .
	uv run mypy
	uv run pyright
	uv run pytest

migrate:        ## Apply migrations
	uv run alembic upgrade head

revision:       ## Autogenerate a migration: make revision m="message"
	uv run alembic revision --autogenerate -m "$(m)"

up:             ## Build and start the full stack (api + postgres)
	docker compose up --build

down:           ## Stop the stack and remove volumes
	docker compose down -v
