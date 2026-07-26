"""Shared test fixtures.

Integration tests run the full app (routers, DI container, use cases, ORM)
against an in-memory SQLite database, so they exercise real wiring without
needing Postgres. Each test gets a fresh app + schema for isolation.

External-service adapters are swapped for in-memory doubles through the
container's ``extra_providers`` seam (``override=True`` wins over the default
binding) — the documented recipe for overriding any port in tests.
"""

from collections.abc import AsyncIterator, Iterator

import pytest
from dishka import AsyncContainer
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import (
    AppSettings,
    DatabaseSettings,
    Environment,
    JwtSettings,
    RateLimitSettings,
    Settings,
    get_settings,
)
from app.infrastructure.database.models.base import Base
from app.main import create_app
from tests.fakes import InMemoryAdaptersProvider


def make_test_settings(
    *,
    auth_rate_limit_requests: int = 100,
    allowed_hosts: list[str] | None = None,
) -> Settings:
    return Settings(
        environment=Environment.TEST,
        # debug=False keeps Starlette's debug tracebacks out of the way so the
        # catch-all problem+json handler is exercised exactly as in production.
        app=AppSettings(
            name="test",
            debug=False,
            allowed_hosts=allowed_hosts if allowed_hosts is not None else ["*"],
        ),
        database=DatabaseSettings(url=SecretStr("sqlite+aiosqlite:///:memory:")),
        jwt=JwtSettings(
            secret=SecretStr("test-secret-key-please-change-0123456789")  # >=32 bytes
        ),
        rate_limit=RateLimitSettings(auth_requests=auth_rate_limit_requests),
    )


async def build_test_app(settings: Settings) -> FastAPI:
    """Creates the app with test overrides and a fresh schema."""
    application = create_app(settings, extra_providers=(InMemoryAdaptersProvider(),))
    container: AsyncContainer = application.state.dishka_container
    engine = await container.get(AsyncEngine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return application


@pytest.fixture(autouse=True)
def reset_settings_cache() -> Iterator[None]:
    """Keep ``get_settings()`` from leaking cached state between tests."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def app() -> AsyncIterator[FastAPI]:
    application = await build_test_app(make_test_settings())
    container: AsyncContainer = application.state.dishka_container
    yield application
    await container.close()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


@pytest.fixture
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    """Registers a user and returns a valid bearer-token header."""
    credentials = {"email": "fixture-user@example.com", "password": "supersecret"}
    await client.post("/api/v1/auth/register", json=credentials)
    response = await client.post("/api/v1/auth/login", json=credentials)
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
