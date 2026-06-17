"""Users API endpoints."""

from typing import Annotated
from uuid import UUID

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Query, status

from app.api.dependencies.auth import CurrentUser
from app.api.v1.users.schemas import (
    CreateUserRequest,
    UserPageResponse,
    UserResponse,
)
from app.application.users.commands.create_user import (
    CreateUserCommand,
    CreateUserHandler,
)
from app.application.users.queries.get_user import GetUserHandler, GetUserQuery
from app.application.users.queries.list_users import ListUsersHandler, ListUsersQuery

router = APIRouter(prefix="/users", tags=["users"], route_class=DishkaRoute)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
async def create_user(
    body: CreateUserRequest,
    handler: FromDishka[CreateUserHandler],
    _: CurrentUser,
) -> UserResponse:
    view = await handler.execute(
        CreateUserCommand(email=body.email, password=body.password)
    )
    return UserResponse.model_validate(view)


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
    view = await handler.execute(GetUserQuery(user_id=user_id))
    return UserResponse.model_validate(view)


@router.get("", response_model=UserPageResponse)
async def list_users(
    handler: FromDishka[ListUsersHandler],
    _: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> UserPageResponse:
    page = await handler.execute(ListUsersQuery(limit=limit, cursor=cursor))
    return UserPageResponse(
        items=[UserResponse.model_validate(v) for v in page.items],
        next_cursor=page.next_cursor,
    )
