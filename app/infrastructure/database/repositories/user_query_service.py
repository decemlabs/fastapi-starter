"""SQLAlchemy Core read model for users (CQRS query side).

Projects columns straight into :class:`UserView` DTOs, skipping aggregate
rehydration. ``Result.tuples()`` gives statically-typed rows, so no ``Any``
leaks from the row mapping. Listing uses keyset (cursor) pagination, not OFFSET,
so it stays fast on large tables.
"""

import base64
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.shared.dto import Page
from app.application.users.dto import UserView
from app.domain.shared.exceptions import ValidationError
from app.infrastructure.database.models.user import UserModel


def _encode_cursor(user_id: UUID) -> str:
    return base64.urlsafe_b64encode(str(user_id).encode()).decode()


def _decode_cursor(cursor: str) -> UUID:
    try:
        return UUID(base64.urlsafe_b64decode(cursor.encode()).decode())
    except (ValueError, TypeError) as exc:
        raise ValidationError("Invalid pagination cursor.") from exc


class SqlAlchemyUserQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> UserView | None:
        stmt = select(
            UserModel.id,
            UserModel.email,
            UserModel.is_active,
            UserModel.created_at,
        ).where(UserModel.id == user_id)
        row = (await self._session.execute(stmt)).tuples().first()
        if row is None:
            return None
        row_id, email, is_active, created_at = row
        return UserView(
            id=row_id, email=email, is_active=is_active, created_at=created_at
        )

    async def list(self, *, limit: int, cursor: str | None) -> Page[UserView]:
        stmt = (
            select(
                UserModel.id,
                UserModel.email,
                UserModel.is_active,
                UserModel.created_at,
            )
            .order_by(UserModel.id)
            .limit(limit + 1)  # fetch one extra to detect a following page
        )
        if cursor is not None:
            stmt = stmt.where(UserModel.id > _decode_cursor(cursor))

        rows = (await self._session.execute(stmt)).tuples().all()
        has_more = len(rows) > limit
        visible = rows[:limit]
        items = [
            UserView(id=row_id, email=email, is_active=is_active, created_at=created_at)
            for row_id, email, is_active, created_at in visible
        ]
        next_cursor = _encode_cursor(visible[-1][0]) if has_more and visible else None
        return Page(items=items, next_cursor=next_cursor)
