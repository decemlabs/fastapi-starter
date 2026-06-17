"""Value objects for the Users domain.

Value objects are immutable, compared by value, and enforce their own
invariants on construction. They make illegal states unrepresentable.
"""

import re
from dataclasses import dataclass
from typing import Final, Self
from uuid import UUID, uuid4

from app.domain.shared.exceptions import ValidationError

_EMAIL_RE: Final = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True, slots=True)
class UserId:
    """Typed identifier for a User aggregate."""

    value: UUID

    @classmethod
    def new(cls) -> Self:
        return cls(uuid4())

    @classmethod
    def from_str(cls, raw: str) -> Self:
        try:
            return cls(UUID(raw))
        except (ValueError, AttributeError, TypeError) as exc:
            raise ValidationError("Invalid user id.") from exc

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class Email:
    """A syntactically valid, normalised email address."""

    value: str

    def __post_init__(self) -> None:
        normalised = self.value.strip().lower()
        if not _EMAIL_RE.match(normalised):
            raise ValidationError(f"Invalid email address: {self.value!r}")
        # Frozen dataclass: bypass immutability once, to store the normal form.
        object.__setattr__(self, "value", normalised)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class HashedPassword:
    """An already-hashed password. The domain never sees plaintext."""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValidationError("Hashed password must not be empty.")
