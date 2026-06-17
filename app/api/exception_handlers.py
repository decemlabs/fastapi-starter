"""Maps domain errors to RFC 9457 (problem+json) HTTP responses.

The domain raises framework-agnostic errors; this is the single place that
decides their HTTP representation. Add an entry to ``_ERROR_MAP`` when you
introduce a domain error that needs a specific status.
"""

from typing import Final, TypedDict

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.domain.auth.exceptions import InvalidCredentialsError, InvalidTokenError
from app.domain.shared.exceptions import DomainError, ValidationError
from app.domain.users.exceptions import EmailAlreadyExistsError, UserNotFoundError


class ProblemDetail(TypedDict):
    """RFC 9457 problem+json response body."""

    type: str
    title: str
    status: int
    detail: str
    instance: str


# (HTTP status code, stable problem "type" slug, human-readable title)
type _ErrorSpec = tuple[int, str, str]

_ERROR_MAP: Final[dict[type[DomainError], _ErrorSpec]] = {
    UserNotFoundError: (status.HTTP_404_NOT_FOUND, "user-not-found", "User not found"),
    EmailAlreadyExistsError: (
        status.HTTP_409_CONFLICT,
        "email-already-exists",
        "Email already exists",
    ),
    InvalidCredentialsError: (
        status.HTTP_401_UNAUTHORIZED,
        "invalid-credentials",
        "Invalid credentials",
    ),
    InvalidTokenError: (
        status.HTTP_401_UNAUTHORIZED,
        "invalid-token",
        "Invalid token",
    ),
    ValidationError: (422, "validation-error", "Validation error"),
}
_DEFAULT: Final[_ErrorSpec] = (
    status.HTTP_400_BAD_REQUEST,
    "domain-error",
    "Domain error",
)


async def _domain_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Registered only for DomainError; the guard keeps the signature compatible
    # with Starlette's handler type and is defensive against misregistration.
    if not isinstance(exc, DomainError):
        raise exc
    status_code, type_slug, title = _ERROR_MAP.get(type(exc), _DEFAULT)
    body: ProblemDetail = {
        "type": f"about:blank#{type_slug}",
        "title": title,
        "status": status_code,
        "detail": exc.message,
        "instance": request.url.path,
    }
    return JSONResponse(
        status_code=status_code,
        media_type="application/problem+json",
        content=body,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _domain_error_handler)
