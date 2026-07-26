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
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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


def setup_middleware(app: FastAPI, settings: Settings) -> None:
    app.add_middleware(RequestContextMiddleware)
    if settings.app.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.app.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
