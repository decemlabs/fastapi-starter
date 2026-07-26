"""Maps every error path to RFC 9457 (problem+json) HTTP responses.

The domain raises framework-agnostic errors; this is the single place that
decides their HTTP representation. Add an entry to ``_ERROR_MAP`` when you
introduce a domain error that needs a specific status — subclasses inherit
their parent's mapping via MRO lookup.

Request-validation errors, plain ``HTTPException``s, and unhandled exceptions
are normalised to the same problem+json shape, so clients see exactly one
error contract. Unhandled exceptions are logged with the bound request id
before the generic 500 is returned.
"""

from collections.abc import Mapping
from http import HTTPStatus
from typing import Final

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.constants import REQUEST_ID_HEADER
from app.domain.auth.exceptions import InvalidCredentialsError, InvalidTokenError
from app.domain.shared.exceptions import DomainError, ValidationError
from app.domain.users.exceptions import EmailAlreadyExistsError, UserNotFoundError

logger = structlog.get_logger()


class ProblemDetail(BaseModel):
    """RFC 9457 problem+json response body."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None


class ValidationIssue(BaseModel):
    """One machine-readable request-validation failure."""

    loc: str
    msg: str
    type: str


class ValidationProblemDetail(ProblemDetail):
    """Problem body extended with the individual validation failures."""

    errors: list[ValidationIssue] = Field(default_factory=list[ValidationIssue])


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
    ValidationError: (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "validation-error",
        "Validation error",
    ),
}
_DEFAULT: Final[_ErrorSpec] = (
    status.HTTP_400_BAD_REQUEST,
    "domain-error",
    "Domain error",
)


def _spec_for(exc: DomainError) -> _ErrorSpec:
    # Walk the MRO so subclasses inherit their parent's mapping instead of
    # silently degrading to the 400 default.
    for klass in type(exc).__mro__:
        if issubclass(klass, DomainError):
            spec = _ERROR_MAP.get(klass)
            if spec is not None:
                return spec
    return _DEFAULT


def _problem_response(
    request: Request,
    problem: ProblemDetail,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    all_headers = dict(headers) if headers else {}
    if problem.status == status.HTTP_401_UNAUTHORIZED:
        all_headers.setdefault("WWW-Authenticate", "Bearer")
    request_id = getattr(request.state, "request_id", None)
    if isinstance(request_id, str):
        # Handlers invoked outside the context middleware's send path (the
        # catch-all below) still stamp the correlation header themselves.
        all_headers.setdefault(REQUEST_ID_HEADER, request_id)
    return JSONResponse(
        status_code=problem.status,
        media_type="application/problem+json",
        content=problem.model_dump(exclude_none=True),
        headers=all_headers,
    )


async def _domain_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Registered only for DomainError; the guard keeps the signature compatible
    # with Starlette's handler type and is defensive against misregistration.
    if not isinstance(exc, DomainError):
        raise exc
    status_code, type_slug, title = _spec_for(exc)
    logger.warning(
        "request.domain_error",
        error=type(exc).__name__,
        status=status_code,
        path=request.url.path,
    )
    problem = ProblemDetail(
        type=f"about:blank#{type_slug}",
        title=title,
        status=status_code,
        detail=exc.message,
        instance=request.url.path,
    )
    return _problem_response(request, problem)


async def _validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    issues = [
        ValidationIssue(
            loc=".".join(str(part) for part in issue["loc"]),
            msg=str(issue["msg"]),
            type=str(issue["type"]),
        )
        for issue in exc.errors()
    ]
    problem = ValidationProblemDetail(
        type="about:blank#request-validation-error",
        title="Request validation error",
        status=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail="The request body or parameters failed validation.",
        instance=request.url.path,
        errors=issues,
    )
    return _problem_response(request, problem)


async def _http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        raise exc
    try:
        title = HTTPStatus(exc.status_code).phrase
    except ValueError:
        title = "HTTP error"
    problem = ProblemDetail(
        type="about:blank#http-error",
        title=title,
        status=exc.status_code,
        detail=exc.detail,
        instance=request.url.path,
    )
    return _problem_response(request, problem, headers=exc.headers)


async def _unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    # The request id is already bound to the structlog context, so this line
    # is enough to correlate the traceback with the failing request.
    logger.exception(
        "request.unhandled_error",
        error=type(exc).__name__,
        method=request.method,
        path=request.url.path,
    )
    # Error-tracker hook point — one line to opt in, e.g.:
    #   sentry_sdk.capture_exception(exc)
    problem = ProblemDetail(
        title="Internal Server Error",
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="An unexpected error occurred.",
        instance=request.url.path,
    )
    return _problem_response(request, problem)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _domain_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)


_RESPONSE_SPECS: Final[dict[int, tuple[str, type[ProblemDetail]]]] = {
    status.HTTP_401_UNAUTHORIZED: ("Missing or invalid credentials", ProblemDetail),
    status.HTTP_404_NOT_FOUND: ("Resource not found", ProblemDetail),
    status.HTTP_409_CONFLICT: ("Conflicting resource state", ProblemDetail),
    status.HTTP_422_UNPROCESSABLE_CONTENT: (
        "Request validation error",
        ValidationProblemDetail,
    ),
    status.HTTP_429_TOO_MANY_REQUESTS: ("Rate limit exceeded", ProblemDetail),
    status.HTTP_500_INTERNAL_SERVER_ERROR: ("Unexpected server error", ProblemDetail),
}


def problem_responses(*status_codes: int) -> dict[int | str, dict[str, object]]:
    """OpenAPI ``responses`` entries documenting the problem+json contract.

    Usage: ``APIRouter(..., responses=problem_responses(401, 404))``.
    """
    responses: dict[int | str, dict[str, object]] = {}
    for code in status_codes:
        description, model = _RESPONSE_SPECS[code]
        responses[code] = {
            "description": description,
            "content": {
                "application/problem+json": {"schema": model.model_json_schema()}
            },
        }
    return responses
