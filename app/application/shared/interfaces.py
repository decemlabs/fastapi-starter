"""Application-level ports (interfaces) implemented by the infrastructure layer.

These abstractions let use cases stay ignorant of concrete technology (JWT
libraries, password hashers, ORMs). Dependencies point inward: infrastructure
depends on these, not the other way around.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

from app.domain.users.repositories import UserRepository

# The two kinds of token this application issues.
type TokenType = Literal["access", "refresh"]


class Clock(Protocol):
    """Abstraction over 'now', so time-dependent logic is testable."""

    def now(self) -> datetime: ...


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


class TokenService(Protocol):
    """Issues and decodes authentication tokens."""

    def create_access_token(self, subject: str) -> str: ...

    def create_refresh_token(self, subject: str) -> str: ...

    def decode(self, token: str) -> TokenPayload: ...


class UnitOfWork(Protocol):
    """Transactional boundary exposing the aggregate repositories.

    A handler performs its writes through the repositories, then calls
    :meth:`commit`. If it raises before committing, the session is rolled back
    when its scope closes (the DI container owns the session lifecycle).
    """

    users: UserRepository

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
