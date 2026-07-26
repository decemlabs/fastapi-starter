"""Pydantic request/response schemas for the Users API (presentation DTOs).

These live in the presentation layer, co-located with the router. They are the
HTTP contract — distinct from domain entities and application DTOs.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: Annotated[str, Field(min_length=8, max_length=128)]


class UserResponse(BaseModel):
    # from_attributes lets us build this straight from a UserView dataclass.
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    is_active: bool
    created_at: datetime


class UserPageResponse(BaseModel):
    items: list[UserResponse]
    next_cursor: str | None = None
