"""In-memory test doubles for the application's ports.

Every fake satisfies its Protocol structurally — no inheritance needed. Use
them to unit-test handlers without I/O, and (via Dishka provider overrides)
to keep integration tests free of external services and Argon2 cost.
"""

import time
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from dishka import Provider, Scope, provide

from app.application.shared.interfaces import (
    IssuedToken,
    PasswordHasher,
    RateLimitDecision,
    RateLimiter,
    TokenPayload,
)
from app.domain.auth.entities import RefreshTokenRecord
from app.domain.auth.exceptions import InvalidTokenError
from app.domain.shared.events import DomainEvent
from app.domain.users.entities import User
from app.domain.users.value_objects import Email, UserId


class InMemoryAdaptersProvider(Provider):
    """Replaces adapters that need external services with in-memory doubles.

    Passed to ``create_app(extra_providers=...)``; ``override=True`` makes
    these bindings win over the defaults — the documented recipe for swapping
    any port in tests. The stub hasher alone cuts integration-test time
    dramatically (no Argon2 per registration); the real hasher is covered by
    its own unit test.
    """

    scope = Scope.APP

    @provide(override=True)
    def rate_limiter(self) -> RateLimiter:
        return InMemoryRateLimiter()

    @provide(override=True)
    def password_hasher(self) -> PasswordHasher:
        return StubPasswordHasher()


class InMemoryRateLimiter:
    """Fixed-window rate limiter backed by a plain dict (single-process)."""

    def __init__(self) -> None:
        self._windows: dict[str, tuple[float, int]] = {}

    async def check(
        self, key: str, limit: int, window_seconds: int
    ) -> RateLimitDecision:
        now = time.monotonic()
        window_start, count = self._windows.get(key, (now, 0))
        if now - window_start >= window_seconds:
            window_start, count = now, 0
        count += 1
        self._windows[key] = (window_start, count)
        if count > limit:
            remaining = window_seconds - (now - window_start)
            return RateLimitDecision(
                allowed=False, retry_after_seconds=max(1, round(remaining))
            )
        return RateLimitDecision(allowed=True, retry_after_seconds=0)


class StubPasswordHasher:
    """Marker-prefix scheme — no CPU cost, satisfies the async port."""

    def __init__(self) -> None:
        self.hash_calls = 0

    async def hash(self, plain_password: str) -> str:
        self.hash_calls += 1
        return f"stub${plain_password}"

    async def verify(self, plain_password: str, hashed_password: str) -> bool:
        return hashed_password == f"stub${plain_password}"


class FrozenClock:
    """A clock that only moves when told to."""

    def __init__(self, start: datetime | None = None) -> None:
        self._now = start if start is not None else datetime(2026, 1, 1, tzinfo=UTC)

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> None:
        self._now += delta


class FakeTokenService:
    """Deterministic tokens: ``{type}:{subject}:{jti}`` — no crypto."""

    refresh_lifetime = timedelta(days=30)

    def __init__(self, clock: FrozenClock | None = None) -> None:
        self._clock = clock if clock is not None else FrozenClock()

    def create_access_token(self, subject: str) -> str:
        return f"access:{subject}:{uuid4()}"

    def create_refresh_token(self, subject: str, token_id: UUID) -> IssuedToken:
        return IssuedToken(
            token=f"refresh:{subject}:{token_id}",
            expires_at=self._clock.now() + self.refresh_lifetime,
        )

    def decode(self, token: str) -> TokenPayload:
        match token.split(":"):
            case ["access", subject, jti]:
                return TokenPayload(
                    subject=subject, token_type="access", token_id=UUID(jti)
                )
            case ["refresh", subject, jti]:
                return TokenPayload(
                    subject=subject, token_type="refresh", token_id=UUID(jti)
                )
            case _:
                raise InvalidTokenError


class InMemoryUserRepository:
    def __init__(self) -> None:
        self.users: dict[UserId, User] = {}

    async def add(self, user: User) -> None:
        self.users[user.id] = user

    async def update(self, user: User) -> None:
        self.users[user.id] = user

    async def get_by_id(self, user_id: UserId) -> User | None:
        return self.users.get(user_id)

    async def get_by_email(self, email: Email) -> User | None:
        for user in self.users.values():
            if user.email == email:
                return user
        return None

    async def exists_by_email(self, email: Email) -> bool:
        return await self.get_by_email(email) is not None


class InMemoryRefreshTokenRepository:
    def __init__(self) -> None:
        self.records: dict[UUID, RefreshTokenRecord] = {}

    async def add(self, record: RefreshTokenRecord) -> None:
        self.records[record.jti] = record

    async def update(self, record: RefreshTokenRecord) -> None:
        self.records[record.jti] = record

    async def get_by_jti(self, jti: UUID) -> RefreshTokenRecord | None:
        return self.records.get(jti)

    async def revoke_family(self, family_id: UUID, at: datetime) -> None:
        for record in self.records.values():
            if record.family_id == family_id:
                record.revoke(at)

    async def revoke_all_for_user(self, user_id: UserId, at: datetime) -> None:
        for record in self.records.values():
            if record.user_id == user_id:
                record.revoke(at)


class FakeUnitOfWork:
    """Satisfies the UnitOfWork port with in-memory repositories."""

    def __init__(self) -> None:
        self.users = InMemoryUserRepository()
        self.refresh_tokens = InMemoryRefreshTokenRepository()
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class RecordingEventDispatcher:
    def __init__(self) -> None:
        self.dispatched: list[DomainEvent] = []

    async def dispatch(self, events: Sequence[DomainEvent]) -> None:
        self.dispatched.extend(events)
