"""Authentication dependency: resolves the current user from a bearer token.

We resolve services from the per-request Dishka container on ``request.state``,
which keeps this dependency independent of the route's injection style and
avoids leaking the web framework into the application layer.
"""

from typing import Annotated, Final

from dishka import AsyncContainer
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.application.shared.interfaces import TokenService, UnitOfWork
from app.domain.auth.exceptions import InvalidTokenError
from app.domain.shared.exceptions import ValidationError
from app.domain.users.entities import User
from app.domain.users.value_objects import UserId

_bearer: Final = HTTPBearer(auto_error=True)


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> User:
    container: AsyncContainer = request.state.dishka_container
    token_service: TokenService = await container.get(TokenService)
    uow: UnitOfWork = await container.get(UnitOfWork)

    payload = token_service.decode(credentials.credentials)
    if payload.token_type != "access":
        raise InvalidTokenError

    try:
        user_id = UserId.from_str(payload.subject)
    except ValidationError:
        raise InvalidTokenError from None

    user = await uow.users.get_by_id(user_id)
    if user is None or not user.is_active:
        raise InvalidTokenError
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
