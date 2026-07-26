.DEFAULT_GOAL := help
.PHONY: help install hooks run test test-pg cov lint fmt format-check typecheck \
        lint-imports check migrate revision downgrade history seed \
        up watch down nuke logs clean

help:           ## List available targets
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install:        ## Install all dependencies (incl. dev group)
	uv sync

hooks:          ## Install pre-commit hooks
	uv run pre-commit install

run:            ## Run the dev server with autoreload
	uv run uvicorn app.main:app --reload

test:           ## Fast test suite (unit + SQLite integration)
	uv run pytest

test-pg:        ## Postgres tier: real DB + migrations (needs Docker)
	uv run pytest -m pg

cov:            ## Tests with branch coverage (fails under the configured gate)
	uv run pytest --cov

lint:           ## Lint with ruff
	uv run ruff check .

fmt:            ## Format with ruff
	uv run ruff format .

format-check:   ## Verify formatting without changing files
	uv run ruff format --check .

typecheck:      ## Static type checking (mypy strict + pyright strict)
	uv run mypy
	uv run pyright

lint-imports:   ## Verify Clean Architecture layer contracts
	uv run lint-imports

check:          ## Run every gate: lint, format, types, contracts, tests+coverage
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy
	uv run pyright
	uv run lint-imports
	uv run pytest --cov

migrate:        ## Apply migrations
	uv run alembic upgrade head

revision:       ## Autogenerate a migration: make revision m="message"
	uv run alembic revision --autogenerate -m "$(m)"

downgrade:      ## Revert the most recent migration
	uv run alembic downgrade -1

history:        ## Show the migration history
	uv run alembic history --verbose

seed:           ## Create the demo user (canonical DI-outside-HTTP example)
	uv run python -m scripts.seed

up:             ## Build and start the full stack, detached
	docker compose up --build -d

watch:          ## Start the stack with live code sync (docker compose watch)
	docker compose up --build --watch

down:           ## Stop the stack (data volumes are kept)
	docker compose down

nuke:           ## Stop the stack AND delete data volumes
	docker compose down -v

logs:           ## Tail api logs
	docker compose logs -f api

clean:          ## Remove caches and coverage artifacts
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
