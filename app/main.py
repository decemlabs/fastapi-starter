"""Application entry point and FastAPI factory.

``create_app`` accepts an optional ``Settings`` so tests can build an app with
an isolated configuration (e.g. an in-memory database).
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from dishka import AsyncContainer
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI

from app.api.exception_handlers import register_exception_handlers
from app.api.middleware import setup_middleware
from app.api.v1.router import api_v1_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.ioc.container import create_container


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings if settings is not None else get_settings()
    configure_logging(resolved)

    container: AsyncContainer = create_container(resolved)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        yield
        await container.close()

    app = FastAPI(
        title=resolved.app.name,
        debug=resolved.app.debug,
        lifespan=lifespan,
    )
    setup_dishka(container, app)
    setup_middleware(app, resolved)
    register_exception_handlers(app)
    app.include_router(api_v1_router)
    return app


app = create_app()
