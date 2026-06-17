# fastapi-starter

Production-grade FastAPI backend template: **Clean Architecture**, **DDD-lite**,
**CQRS-lite**, async-first, and **fully type-safe** — mypy and pyright both pass
in strict mode with zero warnings.

## Features

- **Clean Architecture** — strict layer boundaries; the domain depends on nothing.
- **DDD-lite** — aggregates, value objects, repository ports.
- **CQRS-lite** — command handlers (write) and query services (read) split cleanly.
- **Dependency Injection** — Dishka, with `APP`/`REQUEST` scopes, wired in one composition root.
- **SQLAlchemy 2.0** async + Alembic; domain entities mapped separately from ORM models.
- **Auth** — JWT access/refresh (PyJWT) + Argon2 hashing (pwdlib).
- **Strict typing** — modern hints throughout; no `Any`, `cast`, or `# type: ignore`.
- Cursor pagination, RFC 9457 errors, structured logging, health probes, Docker, tests.

## Stack

| Concern          | Choice                                  |
| ---------------- | --------------------------------------- |
| Web / validation | FastAPI · Pydantic v2                   |
| Persistence      | SQLAlchemy 2.0 (async, asyncpg) · Alembic |
| DI               | Dishka                                  |
| Auth             | PyJWT · pwdlib[argon2]                  |
| Tooling          | uv · ruff · mypy · pyright · pytest     |

## Quick start

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
cp .env.example .env        # then set JWT__SECRET
make install                # uv sync --extra dev
make up                     # Docker: Postgres + migrations + API on :8000
```

Run locally against your own Postgres:

```bash
make migrate && make run    # → http://localhost:8000/docs
```

## Quality gates

Every gate passes with zero warnings. Run them all at once:

```bash
make check                  # ruff · mypy --strict · pyright (strict) · pytest
```

| Gate              | Enforces                                        |
| ----------------- | ----------------------------------------------- |
| `ruff`            | lint, import order, full annotation coverage    |
| `mypy --strict`   | static types (primary checker)                  |
| `pyright` strict  | static types (second, independent checker)      |
| `pytest`          | unit + integration tests (in-memory SQLite)     |

## Layout

```
app/
├── domain/          # entities, value objects, repo ports — pure, no I/O
├── application/     # use cases: commands, queries, ports, DTOs
├── infrastructure/  # adapters: SQLAlchemy, JWT, hashing (+ cache/messaging/storage stubs)
├── ioc/             # Dishka composition root
├── api/             # FastAPI routers, schemas, deps, error mapping
├── core/            # config, logging, constants
└── main.py          # app factory
migrations/   tests/
```

## Architecture

Source dependencies point inward only: `api → application → domain`.
Infrastructure implements the inner layers' ports and is wired in `ioc/`; the
domain knows nothing about FastAPI, SQLAlchemy, or JWT.

See [ARCHITECTURE.md](ARCHITECTURE.md) for layer responsibilities, the request
lifecycle, and a step-by-step guide to adding a feature.

## Make targets

`install` · `run` · `test` · `lint` · `fmt` · `typecheck` · `check` · `migrate` · `revision` · `up` · `down`
