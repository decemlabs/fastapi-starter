"""HTTP middleware: per-request id binding, access logging, and CORS.

``RequestContextMiddleware`` is pure ASGI (no ``BaseHTTPMiddleware``): it adds
no per-request task overhead and keeps the structlog context alive until the
response has actually been sent, including streamed bodies.
"""

import re
import time
import uuid
from typing import Final

import structlog
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import Settings
from app.core.constants import REQUEST_ID_HEADER

logger = structlog.get_logger()

# Inbound ids are propagated only when they look like ids; anything else is
# replaced, so a client cannot inject log content or an oversized header.
_REQUEST_ID_RE: Final = re.compile(r"[A-Za-z0-9._\-]{1,64}")


def _resolve_request_id(raw: str | None) -> str:
    if raw is not None and _REQUEST_ID_RE.fullmatch(raw):
        return raw
    return str(uuid.uuid4())


class RequestContextMiddleware:
    """Binds a request id to the structlog context and emits one access log.

    The id is also stored in ``scope["state"]`` so exception handlers that run
    outside this middleware's send path (the catch-all 500 handler) can stamp
    the correlation header themselves.
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        request_id = _resolve_request_id(headers.get(REQUEST_ID_HEADER))
        scope.setdefault("state", {})
        scope["state"]["request_id"] = request_id
        structlog.contextvars.bind_contextvars(request_id=request_id)

        status_code = 500
        start = time.perf_counter()

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message).setdefault(REQUEST_ID_HEADER, request_id)
            await send(message)

        try:
            await self._app(scope, receive, send_with_request_id)
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            # request_id is also merged from contextvars; passing it explicitly
            # keeps the access event self-contained under any processor chain.
            logger.info(
                "http.request",
                method=scope["method"],
                path=scope["path"],
                status=status_code,
                duration_ms=round(duration_ms, 2),
                request_id=request_id,
            )
            structlog.contextvars.clear_contextvars()


class SecurityHeadersMiddleware:
    """Stamps baseline security headers on every response (pure ASGI)."""

    def __init__(self, app: ASGIApp, *, hsts: bool) -> None:
        self._app = app
        self._hsts = hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.setdefault("X-Content-Type-Options", "nosniff")
                headers.setdefault("X-Frame-Options", "DENY")
                headers.setdefault("Referrer-Policy", "no-referrer")
                headers.setdefault(
                    "Permissions-Policy", "geolocation=(), camera=(), microphone=()"
                )
                if self._hsts:
                    headers.setdefault(
                        "Strict-Transport-Security",
                        "max-age=63072000; includeSubDomains",
                    )
            await send(message)

        await self._app(scope, receive, send_with_headers)


class BodySizeLimitMiddleware:
    """Rejects request bodies over the configured cap with a 413 (pure ASGI).

    The overflow is raised while the downstream handler reads the body, so it
    surfaces through the normal exception handlers as problem+json.
    """

    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self._app = app
        self._max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self._max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail="Request body too large.",
                    )
            return message

        await self._app(scope, limited_receive, send)


def setup_middleware(app: FastAPI, settings: Settings) -> None:
    # add_middleware() wraps outside-in: the LAST one added is the outermost.
    # Effective order: CORS → request context/access log → TrustedHost → GZip
    # → security headers → body cap → routing.
    app.add_middleware(
        BodySizeLimitMiddleware, max_bytes=settings.app.max_request_body_bytes
    )
    app.add_middleware(SecurityHeadersMiddleware, hsts=settings.is_production)
    app.add_middleware(GZipMiddleware)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.app.allowed_hosts)
    app.add_middleware(RequestContextMiddleware)
    if settings.app.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.app.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", REQUEST_ID_HEADER],
            # Without this, browser JS cannot read the correlation id it needs
            # to report alongside errors.
            expose_headers=[REQUEST_ID_HEADER],
        )
