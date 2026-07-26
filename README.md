# fastapi-starter

Production-grade FastAPI backend template: **Clean Architecture**, **DDD-lite**,
**CQRS-lite**, async-first, and **fully type-safe** — mypy and pyright both pass
in strict mode with zero warnings, and the layer boundaries are
machine-enforced.

## Features

- **Clean Architecture** — strict layer boundaries, verified by import-linter
  in CI; the domain depends on nothing.
- **DDD-lite** — aggregates, value objects, repository ports, live domain
  events with an in-process dispatcher (transactional outbox documented as the
  upgrade path).
- **CQRS-lite** — command handlers (write) and query services (read) split cleanly.
- **Dependency Injection** — Dishka, `APP`/`REQUEST` scopes, one composition
  root, and a provider-override seam for tests.
- **SQLAlchemy 2.0** async + Alembic; domain entities mapped separately from
  ORM models; migrations exercised against real Postgres in tests.
- **Auth, production-shaped** — JWT access/refresh (PyJWT, `jti`/`iss`/`aud`),
  refresh rotation with reuse detection, logout, session revocation on
  password change, Argon2 hashing off the event loop, Redis-backed rate
  limiting on the public auth endpoints.
- **One error contract** — RFC 9457 `application/problem+json` on every error
  path (domain, validation, HTTP, unhandled 500), with `WWW-Authenticate` and
  request-id correlation headers.
- **Operable** — structured logging (structlog + stdlib bridge, access log
  with request ids), health probes, security headers, TrustedHost, body-size
  cap, graceful shutdown, and flag-gated OpenTelemetry traces/metrics.
- **Fail-fast configuration** — unsafe production settings (default JWT
  secret, debug mode, wildcard CORS/hosts) abort startup.
- Cursor pagination, Docker with a reproducible uv-locked build, coverage
  gate, pre-commit, GitHub Actions CI.

## Stack

| Concern          | Choice                                     |
| ---------------- | ------------------------------------------ |
| Web / validation | FastAPI · Pydantic v2                      |
| Persistence      | SQLAlchemy 2.0 (async, asyncpg) · Alembic  |
| DI               | Dishka                                     |
| Auth             | PyJWT · pwdlib[argon2]                     |
| Rate limiting    | redis (asyncio)                            |
| Observability    | structlog · OpenTelemetry (optional group) |
| Tooling          | uv · ruff · mypy · pyright · import-linter · pytest · testcontainers |

## Quick start

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
cp .env.example .env        # then set JWT__SECRET
make install                # uv sync (dev group included)
make up                     # Docker: Postgres + Redis + migrations + API on :8000
```

Run locally against your own Postgres/Redis:

```bash
make migrate && make run    # → http://localhost:8000/docs
```

Useful next steps: `make seed` (demo user), `make watch` (compose with live
code sync), `make help` (everything else).

## Start your project

1. On GitHub, click **Use this template** (or clone and re-init git).
2. Rename: the string `fastapi-starter` lives in `pyproject.toml` (`name`),
   `app/main.py` (`_DIST_NAME`), `app/core/config.py` (`AppSettings.name`,
   `JwtSettings.issuer/audience`), `.env.example` (`APP__NAME`), and this
   README's title.
3. Set a real `JWT__SECRET` in `.env`
   (`python -c "import secrets; print(secrets.token_urlsafe(64))"`).
4. `make install && make hooks && make check` — everything must be green
   before you write a line.
5. Keep or strip the `User`/auth demo slice; it is the copyable reference for
   the 7-step add-a-feature walkthrough in
   [ARCHITECTURE.md](ARCHITECTURE.md).
6. Update `LICENSE` with your name/entity.

## Quality gates

Every gate passes with zero warnings. Run them all at once:

```bash
make check    # ruff · format · mypy --strict · pyright (strict) · import-linter · pytest --cov
```

| Gate              | Enforces                                          |
| ----------------- | ------------------------------------------------- |
| `ruff` (+format)  | lint, import order, full annotation coverage      |
| `mypy --strict`   | static types (primary checker)                    |
| `pyright` strict  | static types (second, independent checker)        |
| `import-linter`   | the Clean Architecture dependency rule            |
| `pytest --cov`    | unit + integration tests, branch coverage ≥ 85%   |
| `make test-pg`    | real Postgres: migration chain, dialect, drift    |

CI (GitHub Actions) runs all of the above plus a Docker build that executes
the suite **inside the built image**.

## Testing tiers

- **Unit** — domain and application handlers over in-memory fakes
  (`tests/fakes`, one per port; no I/O, no Argon2).
- **Integration** — the real app end to end over in-memory SQLite; external
  adapters (Redis, Argon2) swapped via a Dishka provider override.
- **Postgres** (`make test-pg`, needs Docker) — testcontainers `postgres:17`:
  the real Alembic chain, concurrent unique-constraint races, and an
  autogenerate drift check (models == migrations, always).

## Layout

```
app/
├── domain/          # entities, value objects, events, repo ports — pure, no I/O
├── application/     # use cases: commands, queries, ports, DTOs
├── infrastructure/  # adapters: SQLAlchemy, JWT, hashing, Redis, events (+ cache/storage stubs)
├── ioc/             # Dishka composition root (providers + handler wiring)
├── api/             # FastAPI routers, schemas, deps, middleware, error mapping
├── core/            # config, logging, telemetry, constants
└── main.py          # app factory
migrations/   scripts/   tests/
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for layer responsibilities, the request
lifecycle, and the step-by-step guide to adding a feature.
[CLAUDE.md](CLAUDE.md) encodes the same invariants for AI coding agents.

## Intentionally not included (and how to add it)

Deliberate omissions — each has a documented seam, so absence is a choice,
not an oversight:

- **Authorization / RBAC** — roles vs scopes vs policies diverge per project.
  Add a `require_permission` dependency factory next to
  `app/api/dependencies/auth.py` and scope the user read/list endpoints.
- **Email verification / password reset** — needs a provider choice and
  token tables. Sketch: `EmailSender` port + a `UserRegistered` handler (see
  `app/infrastructure/messaging/README.md`).
- **Background jobs (taskiq/arq)** — reuse the Dishka container outside HTTP
  the way `scripts/seed.py` does; enqueue from event handlers.
- **Transactional outbox** — the upgrade path from the in-process event
  dispatcher, described step by step in the messaging README.
- **Caching adapter** — `app/infrastructure/cache/README.md` documents the
  port-first recipe (the Redis client is already provided for rate limiting).
- **WebSockets/SSE, API-versioning machinery, a second demo aggregate, code
  generators** — omitted as template bloat; the existing slice plus the
  walkthrough carries the pattern.

## License

[MIT](LICENSE).
