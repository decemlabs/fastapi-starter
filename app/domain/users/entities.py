"""The User aggregate."""

from dataclasses import dataclass
from datetime import datetime
from typing import Self

from app.domain.shared.entity import AggregateRoot
from app.domain.users.events import UserRegistered
from app.domain.users.value_objects import Email, HashedPassword, UserId


@dataclass(eq=False)
class User(AggregateRoot[UserId]):
    """An account holder.

    Construct via :meth:`create` rather than the initialiser directly, so
    invariants and defaults live in one place.
    """

    id: UserId
    email: Email
    hashed_password: HashedPassword
    is_active: bool
    created_at: datetime

    def identity(self) -> UserId:
        return self.id

    @classmethod
    def create(
        cls,
        *,
        user_id: UserId,
        email: Email,
        hashed_password: HashedPassword,
        created_at: datetime,
    ) -> Self:
        user = cls(
            id=user_id,
            email=email,
            hashed_password=hashed_password,
            is_active=True,
            created_at=created_at,
        )
        user.record_event(
            UserRegistered(
                user_id=user_id.value,
                email=str(email),
                occurred_at=created_at,
            )
        )
        return user

    def deactivate(self) -> None:
        self.is_active = False

    def change_password(self, hashed_password: HashedPassword) -> None:
        self.hashed_password = hashed_password
