# CLAUDE.md — invariants for AI-assisted development

Read ARCHITECTURE.md first. These are the rules an agent must not break;
most are machine-checked, all are reviewed.

## The dependency rule (machine-enforced by import-linter)

```
api  →  application  →  domain  ←  infrastructure
                                    (ioc wires everything)
```

- `app/domain`: stdlib only. Never import fastapi, sqlalchemy, pydantic,
  dishka, structlog, redis, jwt, pwdlib, or any other app layer.
- `app/application`: may import `app.domain` only. Same third-party bans.
- `app/api`: never imports `app.infrastructure` or `app.ioc`.
- `app/ioc` is the only place that sees every layer at once.
- Violations fail `make check` (`uv run lint-imports`).

## Typing

- mypy --strict and pyright strict both pass with **zero** errors/warnings.
- No `Any`, no `cast`, no `# type: ignore` in code. Checker relaxations, when
  a third-party library forces one, are scoped in pyproject.toml with a
  comment explaining exactly why (see the Dishka/redis/OTel precedents).

## Where things go

- New domain error → subclass `DomainError`; map it in `_ERROR_MAP`
  (app/api/exception_handlers.py). Subclasses inherit mappings via MRO.
- New port → `Protocol`, declared in the layer that consumes it
  (domain/*/repositories.py or application/shared/interfaces.py).
- New adapter → app/infrastructure/…, wired in app/ioc/providers/.
- ORM models never leave infrastructure; mappers translate (and normalise
  datetimes to aware UTC — SQLite returns naive).
- The unique constraint, not a pre-check, is the source of truth; translate
  IntegrityError to a domain error in the UnitOfWork.
- New aggregate → follow the 7-step walkthrough in ARCHITECTURE.md; the User
  slice is the copyable reference (including the update path).
- Test doubles live in tests/fakes; override container bindings with an
  `override=True` provider passed through `create_app(extra_providers=...)`.

## Testing tiers

- `make test` — fast: unit + integration over in-memory SQLite, stub hasher.
- `make test-pg` — real Postgres via testcontainers: migration chain,
  dialect behaviour, autogenerate drift check. Needs Docker.
- New feature = handler unit tests over fakes + at least one integration
  test; anything dialect- or migration-sensitive goes in tests/integration_pg.

## Before declaring work done

Run `make check` (ruff, format, mypy, pyright, import contracts, tests with
the coverage gate). All of it must pass with zero warnings.
