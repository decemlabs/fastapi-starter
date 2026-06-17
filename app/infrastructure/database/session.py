"""Engine and session-factory construction."""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.core.config import DatabaseSettings


def create_engine(settings: DatabaseSettings) -> AsyncEngine:
    if settings.url.startswith("sqlite"):
        # In-memory SQLite (used in tests) needs a single shared connection.
        return create_async_engine(
            settings.url,
            echo=settings.echo,
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
    return create_async_engine(
        settings.url,
        echo=settings.echo,
        pool_size=settings.pool_size,
        max_overflow=settings.max_overflow,
        pool_pre_ping=True,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
