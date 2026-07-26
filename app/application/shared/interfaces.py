"""Application-level ports (interfaces) implemented by the infrastructure layer.

These abstractions let use cases stay ignorant of concrete technology (JWT
libraries, password hashers, ORMs). Dependencies point inward: infrastructure
depends on these, not the other way around.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from app.domain.auth.repositories import RefreshTokenRepository
from app.domain.shared.events import DomainEvent
from app.domain.users.repositories import UserRepository

# The two kinds of token this application issues.
type TokenType = Literal["access", "refresh"]


class Clock(Protocol):
    """Abstraction over 'now', so time-dependent logic is testable."""

    def now(self) -> datetime: ...


class EventDispatcher(Protocol):
    """Delivers domain events after a successful commit.

    The in-process adapter is the lean default; a transactional outbox is the
    production upgrade path (see app/infrastructure/messaging/README.md).
    """

    async def dispatch(self, events: Sequence[DomainEvent]) -> None: ...


class PasswordHasher(Protocol):
    """Hashes and verifies passwords. The algorithm lives in infrastructure.

    Async because password hashing is deliberately CPU-expensive: adapters
    offload to a worker thread so the event loop keeps serving requests.
    """

    async def hash(self, plain_password: str) -> str: ...

    async def verify(self, plain_password: str, hashed_password: str) -> bool: ...


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    """Outcome of a rate-limit check."""

    allowed: bool
    retry_after_seconds: int


class RateLimiter(Protocol):
    """Counts requests per key within a time window (backend in infrastructure)."""

    async def check(
        self, key: str, limit: int, window_seconds: int
    ) -> RateLimitDecision: ...


@dataclass(frozen=True, slots=True)
class TokenPayload:
    """Decoded token claims relevant to the application."""

    subject: str
    token_type: TokenType
    token_id: UUID


@dataclass(frozen=True, slots=True)
class IssuedToken:
    """A freshly signed token plus the metadata the caller must persist."""

    token: str
    expires_at: datetime


class TokenService(Protocol):
    """Issues and decodes authentication tokens.

    Refresh tokens carry a caller-supplied ``jti`` so the caller can persist
    a matching server-side record (rotation/revocation state).
    """

    def create_access_token(self, subject: str) -> str: ...

    def create_refresh_token(self, subject: str, token_id: UUID) -> IssuedToken: ...

    def decode(self, token: str) -> TokenPayload: ...


class UnitOfWork(Protocol):
    """Transactional boundary exposing the aggregate repositories.

    A handler performs its writes through the repositories, then calls
    :meth:`commit`. If it raises before committing, the session is rolled back
    when its scope closes (the DI container owns the session lifecycle).
    """

    users: UserRepository
    refresh_tokens: RefreshTokenRepository

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
