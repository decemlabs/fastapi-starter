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
    """Hashes and verifies passwords. The algorithm lives in infrastructure."""

    def hash(self, plain_password: str) -> str: ...

    def verify(self, plain_password: str, hashed_password: str) -> bool: ...


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
