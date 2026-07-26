"""Application entry point and FastAPI factory.

``create_app`` accepts an optional ``Settings`` so tests can build an app with
an isolated configuration (e.g. an in-memory database).
"""

from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version

import structlog
from dishka import AsyncContainer, Provider
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI

from app.api.exception_handlers import register_exception_handlers
from app.api.middleware import setup_middleware
from app.api.v1.router import api_v1_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.ioc.container import create_container

logger = structlog.get_logger()

# Distribution name from pyproject.toml — part of the project-rename checklist.
_DIST_NAME = "fastapi-starter"


def _app_version() -> str:
    try:
        return version(_DIST_NAME)
    except PackageNotFoundError:  # running from a plain checkout
        return "0.0.0"


def create_app(
    settings: Settings | None = None,
    extra_providers: Sequence[Provider] = (),
) -> FastAPI:
    """Builds the application.

    ``extra_providers`` is the test seam: providers declared with
    ``override=True`` replace default container bindings (e.g. an in-memory
    rate limiter instead of Redis).
    """
    resolved = settings if settings is not None else get_settings()
    configure_logging(resolved)

    container: AsyncContainer = create_container(resolved, *extra_providers)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        logger.info(
            "app.startup",
            app=resolved.app.name,
            environment=resolved.environment,
            debug=resolved.app.debug,
        )
        yield
        await container.close()
        logger.info("app.shutdown", app=resolved.app.name)

    app = FastAPI(
        title=resolved.app.name,
        version=_app_version(),
        debug=resolved.app.debug,
        lifespan=lifespan,
        # Interactive docs and the schema are dev/staging conveniences; a
        # production API should not advertise its full surface.
        docs_url=None if resolved.is_production else "/docs",
        redoc_url=None if resolved.is_production else "/redoc",
        openapi_url=None if resolved.is_production else "/openapi.json",
    )
    setup_dishka(container, app)
    setup_middleware(app, resolved)
    register_exception_handlers(app)
    app.include_router(api_v1_router)

    if resolved.observability.enabled:
        # Imported lazily: the base install has no OpenTelemetry packages
        # (they live in the `observability` dependency group).
        from app.core.telemetry import configure_telemetry

        configure_telemetry(app, resolved)

    return app


app = create_app()
