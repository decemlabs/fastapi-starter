# Architecture

This document explains the *why* behind the structure and shows how to extend it.

## The dependency rule

Source code dependencies point in one direction only — inward:

```
api  →  application  →  domain  ←  infrastructure
                                   (implements the ports the inner layers declare)
```

- **domain** imports nothing from the project's other layers (only stdlib).
- **application** imports **domain**.
- **infrastructure** imports **application** + **domain** (to implement their
  ports), but no inner layer imports **infrastructure**.
- **api** imports **application** (and **domain** types it surfaces).
- **ioc** is the only place that imports everything, to wire ports to adapters.

This keeps business rules independent of frameworks and databases, so they are
fast to test and slow to rot.

## Layers

### domain (`app/domain/`)
Enterprise rules with zero I/O. Contains:
- **Value objects** (`Email`, `UserId`, `HashedPassword`) — immutable, validated
  on construction, compared by value. They make illegal states unrepresentable.
- **Entities / aggregate roots** (`User`) — identity-based equality, behaviour
  and invariants. Construct via factory methods (`User.create`).
- **Repository ports** (`UserRepository`) — `Protocol` interfaces the domain
  depends on; implemented in infrastructure.
- **Domain errors** — framework-agnostic; mapped to HTTP later.

### application (`app/application/`)
Use cases that orchestrate the domain. Contains:
- **Commands** (write) and **queries** (read) — one handler per use case, with
  an `execute()` method. This is **CQRS-lite**: same database, but reads and
  writes take different paths.
  - Writes go through the **`UnitOfWork`** and the domain `UserRepository`
    (load aggregate → mutate → `commit`).
  - Reads go through **`UserQueryService`**, which projects rows straight into
    `UserView` DTOs (no aggregate rehydration) — cheaper and more flexible.
- **Ports** (`app/application/shared/interfaces.py`): `UnitOfWork`,
  `PasswordHasher`, `TokenService`, `Clock`. The application defines what it
  needs; infrastructure provides it.
- **DTOs** — plain dataclasses crossing the application boundary.

### infrastructure (`app/infrastructure/`)
Adapters that implement the ports:
- **ORM models** (`UserModel`) are *separate* from domain entities. Mapping is
  explicit (`mappers/user_mapper.py`) — Data Mapper, not Active Record — so the
  domain never depends on SQLAlchemy.
- **Repositories** translate between aggregates and rows.
- **Unit of work** wraps one `AsyncSession` and controls when to commit.
- **Security** — `JwtTokenService` (PyJWT), `PwdlibPasswordHasher` (Argon2).
- `cache/`, `messaging/`, `storage/` are documented extension points.

### api (`app/api/`)
The HTTP delivery mechanism:
- **Routers** call use-case handlers (injected via Dishka) and translate between
  Pydantic request/response **schemas** and application DTOs.
- **`dependencies/auth.py`** resolves the current user from a bearer token.
- **`exception_handlers.py`** maps domain errors to RFC 9457 `problem+json`.

### ioc (`app/ioc/`)
The **composition root**. Dishka providers bind each port to a concrete adapter
and declare its lifetime (scope). `create_container(settings)` assembles them.

## Dependency injection & scopes

[Dishka](https://dishka.readthedocs.io) manages object lifecycles via scopes:

| Scope     | Lifetime          | Examples                                            |
| --------- | ----------------- | --------------------------------------------------- |
| `APP`     | whole process     | engine, session factory, password hasher, JWT svc   |
| `REQUEST` | one HTTP request  | session, `UnitOfWork`, `UserQueryService`, handlers |

The request-scoped `AsyncSession` is created by an async-generator provider, so
it is opened at request start and closed at request end — and an uncommitted
session **rolls back on close**, giving us transaction safety for free.

Routers use `route_class=DishkaRoute` + `FromDishka[...]` to inject handlers.
The auth dependency resolves services from the per-request container at
`request.state.dishka_container`, so it stays independent of the route style.

## Request lifecycle (write path)

```
POST /api/v1/auth/register
  → RequestContextMiddleware binds a request id
  → Dishka opens a REQUEST scope (new AsyncSession)
  → router.register(handler: CreateUserHandler = FromDishka)
      → handler.execute(CreateUserCommand)
          → Email(...) validates            (domain)
          → uow.users.exists_by_email(...)   (infra repo)
          → User.create(...)                 (domain factory, hashes via port)
          → uow.users.add(user); uow.commit()
      → returns UserView (application DTO)
  → router maps UserView → UserResponse (Pydantic)
  → Dishka closes the scope (session closed)
If a DomainError is raised, exception_handlers maps it to problem+json.
```

## Error handling

The domain raises errors like `EmailAlreadyExistsError` or
`InvalidCredentialsError`. A single handler (registered for the `DomainError`
base) looks the concrete type up in `_ERROR_MAP` and returns the right status
with an RFC 9457 body. To add a new mapping, add one row to that map.

## Adding a feature (e.g. a `Post` aggregate)

1. **domain/posts/** — `entities.py` (`Post`), `value_objects.py`,
   `repositories.py` (`PostRepository` Protocol), `exceptions.py`.
2. **application/posts/** — `commands/create_post.py`, `queries/list_posts.py`,
   `dto.py`, and a `PostQueryService` port if reads need projections. Add a
   `posts: PostRepository` attribute to `UnitOfWork` (and its SQLAlchemy impl).
3. **infrastructure/database/** — `models/post.py`, `mappers/post_mapper.py`,
   `repositories/post_repository.py`, and `post_query_service.py`.
4. **ioc/providers/** — register the new repository/query service/handlers.
5. **api/v1/posts/** — `schemas.py` + `router.py`; include it in
   `api/v1/router.py`.
6. **migrations/** — `make revision m="add posts"` then `make migrate`.
7. **tests/** — unit tests for the aggregate, integration tests for the endpoints.

Each step touches exactly one layer; the compiler/type checker guides you.

## Testing strategy

- **Unit tests** target the domain — pure, no I/O, microsecond-fast.
- **Integration tests** boot the real app (`create_app`) with an in-memory
  SQLite database, exercising routers → DI → use cases → ORM end to end without
  external services. Swapping `DATABASE__URL` is all it takes because the DB is
  behind a port.
