"""Use case: list users with cursor pagination (read side)."""

from dataclasses import dataclass
from typing import Final

from app.application.shared.dto import Page
from app.application.users.dto import UserView
from app.application.users.interfaces import UserQueryService

_DEFAULT_LIMIT: Final = 20
_MAX_LIMIT: Final = 100


@dataclass(frozen=True, slots=True)
class ListUsersQuery:
    limit: int = _DEFAULT_LIMIT
    cursor: str | None = None


class ListUsersHandler:
    def __init__(self, users: UserQueryService) -> None:
        self._users = users

    async def execute(self, query: ListUsersQuery) -> Page[UserView]:
        limit = max(1, min(query.limit, _MAX_LIMIT))
        return await self._users.list(limit=limit, cursor=query.cursor)
