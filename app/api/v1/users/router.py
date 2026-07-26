"""Users API endpoints."""

from typing import Annotated
from uuid import UUID

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Query, status

from app.api.dependencies.auth import CurrentUser
from app.api.exception_handlers import problem_responses
from app.api.v1.users.schemas import (
    ChangePasswordRequest,
    UserPageResponse,
    UserResponse,
)
from app.application.users.commands.change_password import (
    ChangePasswordCommand,
    ChangePasswordHandler,
)
from app.application.users.queries.get_user import GetUserHandler, GetUserQuery
from app.application.users.queries.list_users import ListUsersHandler, ListUsersQuery

router = APIRouter(
    prefix="/users",
    tags=["users"],
    route_class=DishkaRoute,
    responses=problem_responses(401),
)


@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest,
    handler: FromDishka[ChangePasswordHandler],
    current_user: CurrentUser,
) -> None:
    await handler.execute(
        ChangePasswordCommand(
            user_id=current_user.id.value,
            current_password=body.current_password,
            new_password=body.new_password,
        )
    )


@router.get("/me", response_model=UserResponse)
async def read_me(current_user: CurrentUser) -> UserResponse:
    return UserResponse(
        id=current_user.id.value,
        email=str(current_user.email),
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    handler: FromDishka[GetUserHandler],
    _: CurrentUser,
) -> UserResponse:
    """Demo read endpoint.

    In a real project, looking up arbitrary users belongs behind an
    authorization check (see the RBAC extension point in the README).
    """
    view = await handler.execute(GetUserQuery(user_id=user_id))
    return UserResponse.model_validate(view)


@router.get("", response_model=UserPageResponse)
async def list_users(
    handler: FromDishka[ListUsersHandler],
    _: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> UserPageResponse:
    """Demonstrates keyset (cursor) pagination.

    Listing every account is an admin capability — scope it with an
    authorization dependency before shipping (README extension point).
    """
    page = await handler.execute(ListUsersQuery(limit=limit, cursor=cursor))
    return UserPageResponse(
        items=[UserResponse.model_validate(v) for v in page.items],
        next_cursor=page.next_cursor,
    )
